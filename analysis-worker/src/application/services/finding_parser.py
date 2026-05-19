class FindingParser:
    def parse(self, raw: str) -> list[str]:
        if not raw:
            raise ValueError("LLM returned an empty response")
        findings = []
        for line in raw.splitlines():
            line = line.strip().lstrip("-*•").lstrip("0123456789.)").strip()
            if line:
                findings.append(line)
        return findings
