import structlog

logger = structlog.get_logger()


class FindingParser:
    def parse(self, raw: str) -> list[str]:
        if not raw:
            raise ValueError("LLM returned an empty response")
        findings = []
        for line in raw.splitlines():
            line = line.strip().lstrip("-*•").lstrip("0123456789.)").strip()
            if line:
                findings.append(line)
        logger.info("findings_parsed", count=len(findings))
        return findings
