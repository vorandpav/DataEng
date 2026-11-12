import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone

from kazoo.client import KazooClient
from kazoo.exceptions import BadVersionError, ConnectionLoss, SessionExpiredError
from kazoo.recipe.election import Election

from lib import paths
from lib.pairs_calc import (
    control_line,
    dump_checkpoint,
    empty_counters,
    load_checkpoint,
    run_counts,
    write_all_csv,
)


def setup_log(coord_id: str) -> logging.Logger:
    log_path = paths.LOGS / f"coordinator_{coord_id}.log"
    logger = logging.getLogger(coord_id)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logger.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(sh)
    return logger


class Coordinator:
    def __init__(self, coord_id: str, fencing: bool, throttle: float):
        self.id = coord_id
        self.fencing = fencing
        self.throttle = throttle
        self.log = setup_log(coord_id)
        self.zk = KazooClient(
            hosts=paths.ZK_HOSTS,
            timeout=paths.SESSION_TIMEOUT_MS / 1000,
        )
        self.election = None
        self.my_epoch: int | None = None
        self.leader_since: float | None = None

    def ts(self) -> str:
        return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    def ensure_parent(self) -> None:
        self.zk.ensure_path("/lab4")

    def read_epoch(self) -> int:
        if not self.zk.exists(paths.EPOCH):
            self.zk.create(paths.EPOCH, b"0")
            return 0
        return int(self.zk.get(paths.EPOCH)[0])

    def bump_epoch(self) -> int:
        self.ensure_parent()
        self.read_epoch()

        for _ in range(10):
            try:
                stat = self.zk.get(paths.EPOCH)
                new_val = str(int(stat[0]) + 1).encode()
                self.zk.set(paths.EPOCH, new_val, version=stat[1].version)
                return int(new_val)
            except BadVersionError:
                continue

        raise RuntimeError("не удалось увеличить эпоху")

    def save_checkpoint(self, offset: int, counters) -> None:
        data = dump_checkpoint(offset, counters)
        if self.zk.exists(paths.CHECKPOINT):
            self.zk.set(paths.CHECKPOINT, data)
        else:
            self.zk.create(paths.CHECKPOINT, data)

    def load_checkpoint_from_zk(self):
        if not self.zk.exists(paths.CHECKPOINT):
            return 0, empty_counters()
        return load_checkpoint(self.zk.get(paths.CHECKPOINT)[0])

    def publish_result(self, counters) -> None:
        payload = (
            f"coord={self.id} epoch={self.my_epoch} "
            f"{control_line(counters)} ts={self.ts()}"
        ).encode("utf-8")

        if self.fencing:
            epoch_now = self.read_epoch()
            if self.my_epoch != epoch_now:
                self.log.info(
                    f"отклонено: устаревшая эпоха (моя={self.my_epoch}, в ZK={epoch_now})"
                )
                return

        if not self.zk.exists(paths.POINTER):
            self.zk.create(paths.POINTER, payload)
            self.log.info("записал результат (создан указатель, version=0)")
            return

        cur_version = self.zk.get(paths.POINTER)[1].version
        if self.fencing:
            try:
                self.zk.set(paths.POINTER, payload, version=cur_version)
                self.log.info(
                    f"записал результат (version {cur_version} -> {cur_version + 1})"
                )
            except BadVersionError:
                self.log.info(
                    f"BadVersionError: указатель уже version={cur_version + 1}, "
                    "запись отклонена (fencing)"
                )
        else:
            self.zk.set(paths.POINTER, payload)
            new_ver = self.zk.get(paths.POINTER)[1].version
            self.log.info(f"записал результат (version={new_ver})")

    def leader_work(self) -> None:
        self.leader_since = time.perf_counter()
        self.log.info(f"=== стал лидером (id={self.id}, fencing={self.fencing}) ===")

        self.my_epoch = self.bump_epoch()
        self.log.info(f"эпоха лидерства: {self.my_epoch}")

        offset, counters = self.load_checkpoint_from_zk()
        if offset > 0:
            self.log.info(
                f"продолжаю с чекпоинта offset={offset}; {control_line(counters)}"
            )
        else:
            self.log.info("старт с начала файла")

        def epoch_changed() -> bool:
            return self.read_epoch() != self.my_epoch

        def on_chunk(pos, current_counters):
            nonlocal counters
            counters = current_counters
            if self.fencing and epoch_changed():
                self.log.info("потерял лидерство - прекращаю расчёт (fencing=1)")
                raise RuntimeError("lost leadership")
            self.save_checkpoint(pos, current_counters)
            self.log.info(f"чекпоинт offset={pos}; {control_line(current_counters)}")

        t0 = time.perf_counter()
        try:
            final = run_counts(
                paths.CSV,
                offset,
                counters,
                on_chunk,
                throttle_sec=self.throttle,
                should_abort=epoch_changed if self.fencing else None,
            )
        except (ConnectionLoss, SessionExpiredError):
            if not self.fencing:
                raise
            self.log.info("сессия ZK истекла после паузы — переподключаюсь")
            self.zk = KazooClient(
                hosts=paths.ZK_HOSTS,
                timeout=paths.SESSION_TIMEOUT_MS / 1000,
            )
            self.zk.start()
            self.publish_result(counters)
            return
        except RuntimeError as e:
            if "lost leadership" in str(e):
                self.log.info("выход (старый лидер после failover, fencing=1)")
                self.publish_result(counters)
                return
            raise

        elapsed = time.perf_counter() - t0
        self.log.info(f"расчёт завершён за {elapsed:.1f}s; {control_line(final)}")

        singles_path, pairs_path, triples_path = write_all_csv(
            paths.RESULTS, self.id, final
        )
        self.log.info(f"CSV одиночных навыков: {singles_path}")
        self.log.info(f"CSV пар: {pairs_path}")
        self.log.info(f"CSV троек: {triples_path}")

        self.publish_result(final)
        ptr = self.zk.get(paths.POINTER)
        self.log.info(f"указатель в ZK: {ptr[0].decode()} (version={ptr[1].version})")

    def run(self) -> None:
        self.log.info(
            f"старт координатора id={self.id} fencing={self.fencing} "
            f"session_timeout={paths.SESSION_TIMEOUT_MS}ms"
        )
        self.zk.start()
        self.ensure_parent()
        self.election = Election(self.zk, paths.ELECTION)

        self.election.run(self.leader_work)

        self.zk.stop()
        self.log.info("сессия завершена")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--throttle", type=float, default=0.0)
    args = parser.parse_args()

    coord_id = os.environ.get("COORDINATOR_ID", "A")
    fencing = os.environ.get("FENCING", "0") == "1"

    Coordinator(coord_id, fencing, args.throttle).run()


if __name__ == "__main__":
    main()
