"""Web v20C: v19 intacta + worker renderfast."""
from __future__ import annotations

from suiteviagem.web import server as base
from suiteviagem.web import server_v19 as v19

BaseJobs = base.Jobs


class CarWorkerV20C(v19.CarWorker):
    def command(self):
        cmd = super().command()
        idx = cmd.index("suiteviagem.cars_worker")
        cmd[idx] = "suiteviagem.cars_worker_v20c"
        return cmd


class JobsV20C(v19.JobsV19):
    def __init__(self, db):
        BaseJobs.__init__(self, db)
        self.car_worker = CarWorkerV20C(db, self)
        self.car_worker.warm_async()


def main():
    original = base.Jobs
    base.Jobs = JobsV20C
    try:
        base.main()
    finally:
        base.Jobs = original


if __name__ == "__main__":
    main()
