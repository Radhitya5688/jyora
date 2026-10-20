from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

class Restaurant(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    cuisine = models.CharField(max_length=50, db_index=True)
    address = models.CharField(max_length=220, default="Bengaluru, Karnataka")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="restaurants")
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=Decimal("4.2"))
    review_count = models.PositiveIntegerField(default=0)
    delivery_fee = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("25.00"))
    min_order = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("100.00"))
    prep_minutes = models.PositiveSmallIntegerField(default=25)
    is_open = models.BooleanField(default=True)
    image_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def save(self, *args, **kwargs):
        if not self.slug: self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    def __str__(self): return self.name

class MenuCategory(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=60)
    ordering = models.PositiveSmallIntegerField(default=0)
    class Meta: ordering = ["ordering", "name"]
    def __str__(self): return f"{self.restaurant}: {self.name}"

class MenuItem(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="items")
    category = models.ForeignKey(MenuCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name="items")
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=240, blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    portion_grams = models.PositiveSmallIntegerField(null=True, blank=True)
    is_vegetarian = models.BooleanField(default=True)
    is_available = models.BooleanField(default=True)
    image_url = models.URLField(blank=True)
    class Meta: indexes = [models.Index(fields=["name", "is_available"])]
    def __str__(self): return self.name

class Order(models.Model):
    STATUSES = [(s, s.replace("_", " ").title()) for s in ["placed", "accepted", "preparing", "ready", "rider_assigned", "picked_up", "out_for_delivery", "delivered", "cancelled"]]
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="jyora_orders")
    restaurant = models.ForeignKey(Restaurant, on_delete=models.PROTECT, related_name="orders")
    order_number = models.CharField(max_length=14, unique=True)
    status = models.CharField(max_length=24, choices=STATUSES, default="placed", db_index=True)
    subtotal = models.DecimalField(max_digits=9, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=7, decimal_places=2)
    tax = models.DecimalField(max_digits=7, decimal_places=2)
    discount = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=9, decimal_places=2)
    address = models.CharField(max_length=240)
    payment_method = models.CharField(max_length=24, choices=[("cod", "Cash on delivery"), ("demo", "Simulated online payment")])
    prep_minutes = models.PositiveSmallIntegerField(default=25)
    created_at = models.DateTimeField(default=timezone.now)
    accepted_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    def __str__(self): return self.order_number

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    menu_item = models.ForeignKey(MenuItem, null=True, on_delete=models.SET_NULL)
    name_snapshot = models.CharField(max_length=120)
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    quantity = models.PositiveSmallIntegerField()

class Rider(models.Model):
    name = models.CharField(max_length=80)
    is_available = models.BooleanField(default=True)
    travel_minutes = models.PositiveSmallIntegerField(default=8, help_text="Simulated travel time to restaurant")
    def __str__(self): return self.name

class RiderAssignment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="rider_assignment")
    rider = models.ForeignKey(Rider, on_delete=models.PROTECT, related_name="assignments")
    assigned_at = models.DateTimeField(auto_now_add=True)
    arrived_at = models.DateTimeField(null=True, blank=True)

class DeliveryEvent(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="events")
    status = models.CharField(max_length=24)
    created_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=240, blank=True)

class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
    class Meta: unique_together = [("user", "restaurant")]
