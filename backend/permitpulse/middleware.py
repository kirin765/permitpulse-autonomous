from __future__ import annotations

from django.http import HttpRequest

from permitpulse.models import Organization


class OrganizationResolverMiddleware:
    """Attaches an organization to the request based on X-Org-Slug header."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        request.organization = None
        org_slug = request.headers.get("X-Org-Slug")
        if org_slug:
            request.organization = Organization.objects.filter(slug=org_slug).first()
        return self.get_response(request)
