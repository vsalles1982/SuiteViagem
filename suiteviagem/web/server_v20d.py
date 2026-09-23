"""Web v20D: v19 server + persistent network-scout worker."""
from __future__ import annotations

from suiteviagem.web import server as base
from suiteviagem.web import server_v19 as v19

BaseJobs = base.Jobs


class CarWorkerV20D(v19.CarWorker):
    def command(self):
        cmd = super().command()
        idx = cmd.index("suiteviagem.cars_worker")
        cmd[idx] = "suiteviagem.cars_worker_v20d"
        return cmd


class JobsV20D(v19.JobsV19):
    def __init__(self, db):
        BaseJobs.__init__(self, db)
        self.car_worker = CarWorkerV20D(db, self)
        self.car_worker.warm_async()


def main():
    original = base.Jobs
    base.Jobs = JobsV20D
    try:
        base.main()
    finally:
        base.Jobs = original


if __name__ == "__main__":
    main()
