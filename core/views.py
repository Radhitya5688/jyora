import json
from decimal import Decimal, InvalidOperation
from uuid import uuid4
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from .models import Restaurant, MenuItem, Order, OrderItem, DeliveryEvent, Rider, RiderAssignment
from .services import checkout_cost, eta_for, assign_rider, rank_foodwise

def home(request):
    featured = Restaurant.objects.filter(is_open=True).order_by("-rating")[:8]
    popular = MenuItem.objects.filter(is_available=True).select_related("restaurant").order_by("price")[:6]
    return render(request, "core/home.html", {"restaurants": featured, "popular": popular})

def restaurants(request):
    qs = Restaurant.objects.filter(is_open=True).prefetch_related("items")
    q = request.GET.get("q", "").strip()
    cuisine = request.GET.get("cuisine", "")
    veg = request.GET.get("veg", "")
    if q: qs = qs.filter(Q(name__icontains=q) | Q(cuisine__icontains=q) | Q(items__name__icontains=q, items__is_available=True)).distinct()
    if cuisine: qs = qs.filter(cuisine__iexact=cuisine)
    if veg: qs = qs.filter(items__is_vegetarian=True, items__is_available=True).distinct()
    sort = request.GET.get("sort", "rating")
    qs = qs.order_by({"fee": "delivery_fee", "fast": "prep_minutes", "rating": "-rating"}.get(sort, "-rating"))
    cuisines = Restaurant.objects.values_list("cuisine", flat=True).distinct()
    return render(request, "core/restaurants.html", {"restaurants": qs[:60], "cuisines": cuisines, "q": q})

def restaurant_detail(request, slug):
    restaurant = get_object_or_404(Restaurant.objects.prefetch_related("categories__items", "items"), slug=slug)
    pending_item = MenuItem.objects.filter(pk=request.session.get("pending_cart_item"), restaurant=restaurant).first()
    return render(request, "core/restaurant.html", {"restaurant": restaurant, "categories": restaurant.categories.all(), "pending_item": pending_item})

def register(request):
    form = UserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(); login(request, user); messages.success(request, "Welcome to Jyora."); return redirect("home")
    return render(request, "registration/register.html", {"form": form})

def cart_data(request): return request.session.get("cart", {})

def cart(request):
    cart = cart_data(request); items=[]; subtotal=Decimal("0.00"); restaurant=None
    for key, qty in cart.items():
        try: item=MenuItem.objects.select_related("restaurant").get(pk=int(key), is_available=True)
        except (MenuItem.DoesNotExist, ValueError): continue
        restaurant = item.restaurant; line=item.price*int(qty); subtotal += line; items.append({"item": item, "qty": int(qty), "line": line})
    costs = checkout_cost(subtotal, restaurant.delivery_fee if restaurant else 0, request.session.get("coupon", False)) if items else None
    return render(request, "core/cart.html", {"items": items, "restaurant": restaurant, "costs": costs})

def add_to_cart(request, item_id):
    if request.method != "POST": return redirect("cart")
    item=get_object_or_404(MenuItem, pk=item_id, is_available=True)
    cart=cart_data(request); other=[k for k in cart if k != str(item_id) and MenuItem.objects.filter(pk=k).exclude(restaurant=item.restaurant).exists()]
    if other and request.POST.get("replace") != "yes":
        request.session["pending_cart_item"] = item.pk
        messages.warning(request, "Your cart has another restaurant's items. Confirm to replace it.")
        return redirect("restaurant_detail", slug=item.restaurant.slug)
    if other: cart={}
    cart[str(item_id)] = min(20, int(cart.get(str(item_id), 0))+1)
    request.session.pop("pending_cart_item", None)
    request.session["cart"] = cart; request.session.modified=True; messages.success(request, f"{item.name} added to cart.")
    return redirect("cart")

def update_cart(request, item_id):
    if request.method == "POST":
        cart=cart_data(request); qty=request.POST.get("quantity", "0")
        try: qty=max(0, min(20, int(qty)))
        except ValueError: qty=0
        if qty: cart[str(item_id)]=qty
        else: cart.pop(str(item_id), None)
        request.session["cart"]=cart
    return redirect("cart")

@login_required
def checkout(request):
    cart=cart_data(request)
    if not cart: messages.info(request, "Your cart is empty."); return redirect("restaurants")
    items=[]
    for key, qty in cart.items():
        item=get_object_or_404(MenuItem, pk=int(key), is_available=True); items.append((item, int(qty)))
    restaurant=items[0][0].restaurant
    if any(i.restaurant_id != restaurant.id for i,_ in items):
        request.session["cart"]={}; messages.error(request, "Cart validation failed. Please add items from one restaurant."); return redirect("cart")
    subtotal=sum((i.price*q for i,q in items), Decimal("0"))
    costs=checkout_cost(subtotal, restaurant.delivery_fee, request.POST.get("coupon", "").strip().upper()=="SAVE50")
    if request.method == "POST":
        address=request.POST.get("address", "").strip()
        if len(address)<8: messages.error(request, "Enter a delivery address (at least 8 characters).")
        elif request.POST.get("payment") not in ["cod", "demo"]: messages.error(request, "Choose a supported demo payment method.")
        else:
            with transaction.atomic():
                order=Order.objects.create(customer=request.user, restaurant=restaurant, order_number=uuid4().hex[:12].upper(), subtotal=costs["subtotal"], delivery_fee=costs["delivery_fee"], tax=costs["tax"], discount=costs["discount"], total=costs["total"], address=address, payment_method=request.POST["payment"], prep_minutes=restaurant.prep_minutes)
                for item,qty in items: OrderItem.objects.create(order=order, menu_item=item, name_snapshot=item.name, unit_price=item.price, quantity=qty)
                DeliveryEvent.objects.create(order=order, status="placed", note="Order received by Jyora")
            request.session["cart"]={}; request.session.pop("coupon", None); messages.success(request, "Order placed successfully."); return redirect("track_order", order_number=order.order_number)
    return render(request, "core/checkout.html", {"items": items, "restaurant": restaurant, "costs": costs})

@login_required
def order_history(request):
    return render(request, "core/orders.html", {"orders": Order.objects.filter(customer=request.user).select_related("restaurant").order_by("-created_at")})

@login_required
def track_order(request, order_number):
    order=get_object_or_404(Order.objects.select_related("restaurant").prefetch_related("items", "events"), order_number=order_number, customer=request.user)
    return render(request, "core/track.html", {"order": order, "eta": eta_for(order)})

def foodwise(request):
    q=request.GET.get("q", "").strip()
    items=MenuItem.objects.filter(is_available=True).select_related("restaurant")
    if q: items=items.filter(name__iexact=q)
    else: items=items.none()
    rows=[]
    for i in items[:80]:
        c=checkout_cost(i.price, i.restaurant.delivery_fee)
        rows.append({"item":i,"total":c["total"],"portion":i.portion_grams})
    rows=rank_foodwise(rows)
    return render(request, "core/foodwise.html", {"rows":rows,"q":q})

def owned_restaurant(request):
    return Restaurant.objects.filter(owner=request.user).first()

@login_required
def owner_dashboard(request):
    restaurant=owned_restaurant(request)
    if not restaurant: return HttpResponseForbidden("No restaurant is linked to this owner account. Assign one in Django admin.")
    orders=restaurant.orders.exclude(status__in=["delivered","cancelled"]).select_related("customer").prefetch_related("items").order_by("created_at")
    recent=restaurant.orders.filter(status="delivered").order_by("-created_at")[:25]
    avg_prep=sum([o.prep_minutes for o in recent],0)/max(len(recent),1)
    return render(request,"core/owner.html",{"restaurant":restaurant,"orders":orders,"avg_prep":round(avg_prep),"items":restaurant.items.all()})

@login_required
def owner_order_action(request, order_id, action):
    if request.method != "POST": return HttpResponseForbidden("Order actions require a POST request.")
    order=get_object_or_404(Order.objects.select_related("restaurant"),pk=order_id)
    if order.restaurant.owner_id != request.user.id: return HttpResponseForbidden()
    transitions={"accept":("placed","accepted"),"prepare":("accepted","preparing"),"ready":("preparing","ready"),"pickup":("ready","picked_up"),"out":("picked_up","out_for_delivery"),"deliver":("out_for_delivery","delivered")}
    valid = order.status in ["ready", "rider_assigned"] if action == "pickup" else (action in transitions and order.status == transitions[action][0])
    if action not in transitions or not valid: messages.error(request,"That order status change is not allowed.")
    else:
        order.status=transitions[action][1]
        if action=="accept": order.accepted_at=timezone.now()
        if action=="ready": order.ready_at=timezone.now()
        if action=="deliver": order.delivered_at=timezone.now()
        order.save(); DeliveryEvent.objects.create(order=order,status=order.status)
        if action=="ready":
            with transaction.atomic():
                rider=assign_rider(order)
                if rider: DeliveryEvent.objects.create(order=order,status=order.status,note=f"Demo rider {rider.name} assigned; ETA {rider.travel_minutes} minutes")
        messages.success(request,"Order updated.")
    return redirect("owner_dashboard")

@login_required
def toggle_item(request,item_id):
    item=get_object_or_404(MenuItem.objects.select_related("restaurant"),pk=item_id)
    if item.restaurant.owner_id != request.user.id: return HttpResponseForbidden()
    if request.method=="POST": item.is_available=not item.is_available; item.save(update_fields=["is_available"])
    return redirect("owner_dashboard")

def about(request): return render(request,"core/info.html",{"title":"About Jyora","body":"Jyora is a student-built food ordering and restaurant intelligence platform."})
def faq(request): return render(request,"core/info.html",{"title":"Frequently asked questions","body":"Orders are demo orders. Online payment is simulated and no payment details are collected. Delivery estimates are provisional."})
def contact(request): return render(request,"core/info.html",{"title":"Contact","body":"For this local demonstration, contact the project maintainer through the repository."})
