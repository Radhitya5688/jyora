from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Restaurant, MenuItem, Order, Rider
from .services import checkout_cost, eta_for

class JyoraCoreTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user(username="customer",password="safe-pass-123")
        self.r=Restaurant.objects.create(name="Test Kitchen",slug="test-kitchen",cuisine="South Indian",delivery_fee=Decimal("20"),prep_minutes=25)
        self.item=MenuItem.objects.create(restaurant=self.r,name="Masala Dosa",price=Decimal("100"),portion_grams=300)
    def test_server_cost_rules_and_coupon_threshold(self):
        c=checkout_cost(Decimal("500"),Decimal("20"),True)
        self.assertEqual(c["total"],Decimal("500.00"))
        self.assertEqual(checkout_cost(Decimal("100"),Decimal("20"),True)["discount"],Decimal("0.00"))
    def test_menu_discovery_uses_database(self):
        res=self.client.get(reverse("restaurants"),{"q":"dosa"})
        self.assertContains(res,"Test Kitchen")
    def test_foodwise_requires_dish_match_and_omits_missing_portion(self):
        self.assertContains(self.client.get(reverse("foodwise")),"Search an exact dish name")
        self.item.portion_grams=None; self.item.save(update_fields=["portion_grams"])
        response=self.client.get(reverse("foodwise"),{"q":"Masala Dosa"})
        self.assertContains(response,"Not provided")
        self.assertNotContains(response,"neutral 250g")
    def test_cart_and_checkout_pages_render(self):
        self.client.force_login(self.user)
        session=self.client.session; session["cart"]={str(self.item.pk):1}; session.save()
        self.assertEqual(self.client.get(reverse("cart")).status_code,200)
        self.assertEqual(self.client.get(reverse("checkout")).status_code,200)
    def test_cart_checkout_creates_snapshots(self):
        self.client.login(username="customer",password="safe-pass-123")
        session=self.client.session; session["cart"]={str(self.item.pk):2}; session.save()
        response=self.client.post(reverse("checkout"),{"address":"12 Sample Road Bengaluru","payment":"cod"})
        self.assertEqual(response.status_code,302)
        order=Order.objects.get(customer=self.user)
        self.assertEqual(order.items.first().name_snapshot,"Masala Dosa")
        self.assertEqual(order.total,Decimal("235.00"))
    def test_order_privacy_and_eta_provisional(self):
        self.client.login(username="customer",password="safe-pass-123")
        order=Order.objects.create(customer=self.user,restaurant=self.r,order_number="ABCD1234EFGH",subtotal=100,delivery_fee=20,tax=5,total=130,address="Some address",payment_method="cod")
        self.assertEqual(eta_for(order)["confidence"],"Provisional")
        other=User.objects.create_user(username="other",password="safe-pass-123")
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("track_order",args=[order.order_number])).status_code,404)
    def test_cart_refuses_cross_restaurant_until_confirmed(self):
        second=Restaurant.objects.create(name="Other Kitchen",slug="other-kitchen",cuisine="Chinese")
        other_item=MenuItem.objects.create(restaurant=second,name="Noodles",price=150)
        session=self.client.session; session["cart"]={str(self.item.pk):1}; session.save()
        response=self.client.post(reverse("add_to_cart",args=[other_item.pk]))
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.client.session["cart"],{str(self.item.pk):1})
        response=self.client.post(reverse("add_to_cart",args=[other_item.pk]),{"replace":"yes"})
        self.assertEqual(self.client.session["cart"],{str(other_item.pk):1})
    def test_owner_transitions_require_post_and_owner(self):
        owner=User.objects.create_user(username="owner",password="owner-pass-123")
        self.r.owner=owner; self.r.save()
        order=Order.objects.create(customer=self.user,restaurant=self.r,order_number="ORDER0000001",subtotal=100,delivery_fee=20,tax=5,total=130,address="Some address",payment_method="cod")
        self.client.force_login(owner)
        url=reverse("owner_order_action",args=[order.pk,"accept"])
        self.assertEqual(self.client.get(url).status_code,403)
        self.assertEqual(self.client.post(url).status_code,302)
        order.refresh_from_db(); self.assertEqual(order.status,"accepted")
        self.client.post(reverse("owner_order_action",args=[order.pk,"prepare"]))
        Rider.objects.create(name="Available demo rider",travel_minutes=7)
        self.client.post(reverse("owner_order_action",args=[order.pk,"ready"]))
        order.refresh_from_db(); self.assertEqual(order.status,"rider_assigned")
        self.assertTrue(order.rider_assignment)
        self.client.post(reverse("owner_order_action",args=[order.pk,"pickup"]))
        self.client.post(reverse("owner_order_action",args=[order.pk,"out"]))
        self.client.post(reverse("owner_order_action",args=[order.pk,"deliver"]))
        order.refresh_from_db(); self.assertEqual(order.status,"delivered")
        other=User.objects.create_user(username="other-owner",password="owner-pass-123")
        self.client.force_login(other)
        self.assertEqual(self.client.post(reverse("owner_order_action",args=[order.pk,"prepare"])).status_code,403)
