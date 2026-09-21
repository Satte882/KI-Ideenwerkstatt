from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def demo_portal(request):
    return render(request, "portal/home.html")


@login_required
def procurement_case(request):
    return render(request, "portal/case_procurement.html")


@login_required
def sales_conversation_case(request):
    return render(request, "portal/sales_conversation_case.html")
