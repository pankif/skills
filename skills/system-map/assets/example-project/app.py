"""Вымышленная система подготовки отчётов; исходник для примера карты."""


def submit_report(user, request_key, reports, jobs):
    if not user["active"]:
        raise PermissionError("Доступ закрыт")
    if request_key in reports:
        return reports[request_key]
    report = {"id": request_key, "state": "queued"}
    reports[request_key] = report
    jobs.append(request_key)
    return report


def process_next(jobs, reports, render, storage, notify):
    report_id = jobs.pop(0)
    report = reports[report_id]
    report["state"] = "running"
    try:
        content = render(report_id)
        report["url"] = storage.put(report_id, content)
        report["state"] = "ready"
    except Exception:
        report["state"] = "failed"
        raise
    notify(report["url"])


def get_status(report_id, reports):
    report = reports[report_id]
    if report["state"] == "ready":
        return {"state": "ready", "url": report["url"]}
    return {"state": report["state"]}
