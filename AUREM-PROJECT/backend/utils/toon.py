def json_to_toon(data, type_name="Object"):
    if not data:
        return f"{type_name}[0]:"
    if isinstance(data, dict):
        lines = [f"{type_name}:"]
        for k, v in data.items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines)
    keys = list(data[0].keys())
    header = f"{type_name}[{len(data)}]{{{','.join(keys)}}}:"
    rows = [",".join(str(item.get(k, "")) for k in keys) for item in data]
    return f"{header}\n" + "\n".join(rows)
