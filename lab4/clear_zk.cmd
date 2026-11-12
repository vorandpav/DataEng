@echo off
docker exec lab4-zoo1 zkCli.sh -server localhost:2181 deleteall /lab4
