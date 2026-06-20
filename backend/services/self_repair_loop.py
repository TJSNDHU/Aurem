import re
from urllib.parse import urlparse
from typing import Optional

class SelfRepairLoop:
    def __init__(self):
        self.active_tenants = set()

    def validate_website_url(self, url: str) -> bool:
        try:
            result = urlparse(url)
            if not all([result.scheme, result.netloc]):
                return False
            if not re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', result.netloc):
                return False
            return True
        except ValueError:
            return False

    def process_tenant(self, tenant_id: str, website_url: Optional[str] = None) -> bool:
        if tenant_id in self.active_tenants:
            return False

        if website_url and not self.validate_website_url(website_url):
            raise ValueError(f"Invalid website URL format: {website_url}")

        self.active_tenants.add(tenant_id)
        try:
            # Main processing logic here
            return True
        except Exception as e:
            self.active_tenants.remove(tenant_id)
            raise e
