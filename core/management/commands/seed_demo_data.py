from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.text import slugify
from datetime import timedelta
from core.models import Restaurant, MenuCategory, MenuItem, Rider, Order, OrderItem, DeliveryEvent, RiderAssignment

class Command(BaseCommand):
    help = "Create plausible Jyora demonstration restaurants, menus and riders."
    def handle(self,*args,**options):
        data=[("Udupi House","South Indian",4.6,18),("Tandoori Junction","North Indian",4.5,35),("Wok & Roll","Chinese",4.3,25),("Pasta Posto","Italian",4.4,32),("Bun Theory","Burgers",4.2,20),("Namma Dosa","South Indian",4.7,15),("Biryani Darbar","North Indian",4.5,28),("Green Bowl Co.","Healthy",4.3,22),("Choco & Crumb","Desserts",4.6,20),("Coastal Curry Leaf","South Indian",4.4,30)]
        menus={
            "South Indian": [("Masala Dosa",85,True),("Idli Sambar",70,True),("Pongal",110,True),("Rava Dosa",105,True),("Veg Meals",160,True),("Filter Coffee",45,True),("Chicken Biryani",230,False),("Paneer Biryani",210,True)],
            "North Indian": [("Paneer Tikka",220,True),("Chicken Biryani",240,False),("Butter Chicken",260,False),("Paneer Biryani",210,True),("Dal Makhani",185,True),("Butter Naan",45,True),("Gulab Jamun",90,True),("Chole Bhature",150,True)],
            "Chinese": [("Veg Hakka Noodles",165,True),("Chilli Paneer",210,True),("Chicken Fried Rice",220,False),("Veg Manchurian",180,True),("Spring Rolls",135,True),("Schezwan Noodles",185,True),("Momos",160,True),("Honey Chilli Potato",170,True)],
            "Italian": [("Arrabbiata Pasta",260,True),("Margherita Pizza",240,True),("Pesto Pasta",290,True),("Alfredo Pasta",280,True),("Garlic Bread",130,True),("Lasagna",320,True),("Tiramisu",180,True),("Risotto",270,True)],
            "Burgers": [("Classic Veg Burger",145,True),("Crispy Chicken Burger",190,False),("Cheese Fries",130,True),("Paneer Burger",175,True),("Chicken Wings",230,False),("Veg Wrap",150,True),("Brownie",100,True),("Lemonade",70,True)],
            "Healthy": [("Quinoa Power Bowl",240,True),("Paneer Salad",210,True),("Greek Yogurt Bowl",175,True),("Green Smoothie",150,True),("Veggie Wrap",180,True),("Avocado Toast",220,True),("Roasted Veg Bowl",200,True),("Fruit Cup",120,True)],
            "Desserts": [("Chocolate Brownie",120,True),("Cheesecake Slice",220,True),("Gulab Jamun",90,True),("Tiramisu Cup",180,True),("Mango Kulfi",110,True),("Chocolate Tart",190,True),("Cookie Box",140,True),("Ice Cream Sundae",170,True)],
        }
        owner,_=User.objects.get_or_create(username="demo_owner",defaults={"email":"owner@example.test"})
        if not owner.has_usable_password(): owner.set_password("JyoraDemo2026!"); owner.save()
        customer,_=User.objects.get_or_create(username="demo_customer",defaults={"email":"customer@example.test"})
        if not customer.has_usable_password(): customer.set_password("JyoraDemo2026!"); customer.save()
        for n,(name,cuisine,rating,fee) in enumerate(data):
            canonical_slug=slugify(name)
            r=Restaurant.objects.filter(name=name).first()
            if r:
                if r.slug != canonical_slug: r.slug=canonical_slug; r.save(update_fields=["slug"])
            else:
                r=Restaurant.objects.create(slug=canonical_slug,name=name,cuisine=cuisine,rating=Decimal(str(rating)),review_count=120+n*13,delivery_fee=Decimal(fee),prep_minutes=20+(n%4)*5,owner=owner if n==0 else None,description=f"Neighbourhood favourite for freshly prepared {cuisine.lower()} classics.",image_url="https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=900&q=80")
            cat,_=MenuCategory.objects.get_or_create(restaurant=r,name="House favourites")
            menu=menus.get(cuisine, menus["North Indian"])
            allowed_names=[dish for dish,_,_ in menu]
            r.items.exclude(name__in=allowed_names).update(is_available=False)
            for j,(dish,price,veg) in enumerate(menu):
                MenuItem.objects.get_or_create(restaurant=r,name=dish,defaults={"category":cat,"description":"A Jyora demo menu favourite, made fresh to order.","price":Decimal(price+(n%3)*10),"portion_grams":250+(j%3)*50,"is_vegetarian":veg})
        riders=[]
        for i,minutes in enumerate([6,9,12,15]): riders.append(Rider.objects.get_or_create(name=f"Demo Rider {i+1}",defaults={"travel_minutes":minutes})[0])
        restaurant=Restaurant.objects.get(slug="udupi-house")
        item=restaurant.items.first()
        active,_=Order.objects.get_or_create(order_number="JYORADEMO001",defaults={"customer":customer,"restaurant":restaurant,"status":"preparing","subtotal":item.price,"delivery_fee":restaurant.delivery_fee,"tax":(item.price*Decimal("0.05")).quantize(Decimal("0.01")),"total":item.price+restaurant.delivery_fee+Decimal("5")+(item.price*Decimal("0.05")).quantize(Decimal("0.01")),"address":"Demo delivery point, Bengaluru","payment_method":"cod","prep_minutes":restaurant.prep_minutes,"created_at":timezone.now()-timedelta(minutes=12),"accepted_at":timezone.now()-timedelta(minutes=10)})
        if not active.items.exists(): OrderItem.objects.create(order=active,menu_item=item,name_snapshot=item.name,unit_price=item.price,quantity=1)
        if not active.events.exists(): DeliveryEvent.objects.create(order=active,status="preparing",note="Seeded Kitchensync demonstration order")
        past,_=Order.objects.get_or_create(order_number="JYORADEMO002",defaults={"customer":customer,"restaurant":restaurant,"status":"delivered","subtotal":item.price,"delivery_fee":restaurant.delivery_fee,"tax":(item.price*Decimal("0.05")).quantize(Decimal("0.01")),"total":item.price+restaurant.delivery_fee+Decimal("5")+(item.price*Decimal("0.05")).quantize(Decimal("0.01")),"address":"Demo delivery point, Bengaluru","payment_method":"cod","prep_minutes":24,"created_at":timezone.now()-timedelta(days=2),"delivered_at":timezone.now()-timedelta(days=2)+timedelta(minutes=43)})
        if not past.items.exists(): OrderItem.objects.create(order=past,menu_item=item,name_snapshot=item.name,unit_price=item.price,quantity=1)
        if not past.events.exists(): DeliveryEvent.objects.create(order=past,status="delivered",note="Seeded demo history")
        self.stdout.write(self.style.SUCCESS("Seeded 10 restaurants, 80 menu items, 4 simulated riders and 2 clearly marked demo orders."))
