"""Web v20F: v19 server + v20E API fast-path + browser API transport."""
from __future__ import annotations

from suiteviagem.web import server as base
from suiteviagem.web import server_v19 as v19

BaseJobs = base.Jobs


class CarWorkerV20F(v19.CarWorker):
    def command(self):
        cmd = super().command()
        idx = cmd.index("suiteviagem.cars_worker")
        cmd[idx] = "suiteviagem.cars_worker_v20f"
        return cmd


class JobsV20F(v19.JobsV19):
    def __init__(self, db):
        BaseJobs.__init__(self, db)
        self.car_worker = CarWorkerV20F(db, self)
        self.car_worker.warm_async()


def main():
    original = base.Jobs
    base.Jobs = JobsV20F
    try:
        base.main()
    finally:
        base.Jobs = original


if __name__ == "__main__":
    main()
