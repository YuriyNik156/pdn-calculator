def mask_sensitive(data: dict, fields: list = None) -> dict:
    fields = fields or ["client_id", "request_id"]
    masked = data.copy()
    if "meta" in masked:
        for f in fields:
            if f in masked["meta"]:
                masked["meta"][f] = "***"
    return masked
