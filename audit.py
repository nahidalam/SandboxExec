class AuditLog:
    def __init__(self):
        self.entries = []
        self.timeline = []

    def log(self, label: str, payload):
        self.entries.append({"label": label, "payload": payload})
        self.timeline.append(label)

    def json(self):
        return {"entries": self.entries, "timeline": self.timeline}
