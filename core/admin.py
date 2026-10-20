from django.contrib import admin
from .models import Restaurant, MenuCategory, MenuItem, Order, OrderItem, Rider, RiderAssignment, DeliveryEvent, Favorite
class ItemInline(admin.TabularInline): model=MenuItem; extra=0
@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin): list_display=("name","cuisine","owner","rating","is_open"); list_filter=("cuisine","is_open"); search_fields=("name","address"); prepopulated_fields={"slug":("name",)}; inlines=[ItemInline]
class OrderItemInline(admin.TabularInline): model=OrderItem; extra=0; readonly_fields=("name_snapshot","unit_price","quantity")
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin): list_display=("order_number","customer","restaurant","status","total","created_at"); list_filter=("status","restaurant"); search_fields=("order_number","customer__username"); inlines=[OrderItemInline]
admin.site.register([MenuCategory,MenuItem,Rider,RiderAssignment,DeliveryEvent,Favorite])
