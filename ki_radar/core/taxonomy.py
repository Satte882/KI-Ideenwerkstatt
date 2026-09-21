from django.db import models


class BusinessDomain(models.TextChoices):
    PROCUREMENT = "procurement", "Einkauf und Beschaffung"
    SALES = "sales", "Vertrieb"
    MARKETING = "marketing", "Marketing"
    PRODUCTION = "production", "Produktion und Leistungserbringung"
    LOGISTICS = "logistics", "Logistik und Supply Chain"
    FINANCE = "finance", "Finanzen und Controlling"
    HUMAN_RESOURCES = "human_resources", "Personal"
    CUSTOMER_SERVICE = "customer_service", "Kundenservice"
    IT = "it", "IT und Technologie"
    LEGAL_COMPLIANCE = "legal_compliance", "Recht und Compliance"
    RESEARCH_DEVELOPMENT = "research_development", "Forschung und Entwicklung"
    CORPORATE_SERVICES = "corporate_services", "Unternehmensfunktionen"
    OTHER = "other", "Sonstige Fachdomäne"


class ScreeningLevel(models.TextChoices):
    LOW = "low", "Niedrig"
    MEDIUM = "medium", "Mittel"
    HIGH = "high", "Hoch"
