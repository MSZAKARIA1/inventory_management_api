from django.contrib import admin
from .models import InventoryHistory

# Register your models here.
     
@admin.register(InventoryHistory)
class InventoryHistoryAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "action", "quantity_changed", "timestamp")
    list_filter = ("action", "timestamp")
    search_fields = ("product__name", "user__username")
