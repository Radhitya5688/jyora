from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
from django.utils import timezone
from .models import Rider, RiderAssignment

def money(value): return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def checkout_cost(subtotal, delivery_fee, coupon=False):
    """Demo rules: INR 5 platform fee, 5% tax on food, SAVE50 gives INR 50 off orders >= 499."""
    subtotal, delivery_fee = money(subtotal), money(delivery_fee)
    discount = Decimal("50.00") if coupon and subtotal >= 499 else Decimal("0.00")
    tax = money(subtotal * Decimal("0.05"))
    total = max(Decimal("0.00"), subtotal + delivery_fee + Decimal("5.00") + tax - discount)
    return {"subtotal": subtotal, "delivery_fee": delivery_fee, "platform_fee": Decimal("5.00"), "tax": tax, "discount": discount, "total": money(total)}

def foodwise_score(item):
    """Available-feature weighted ranking; normalize prices/fees/speed against comparison set upstream."""
    return item

FOODWISE_WEIGHTS = {"affordability": .35, "rating": .25, "portion": .20, "delivery": .10, "speed": .10}

def rank_foodwise(rows):
    """Score comparable result rows; omit unavailable portion data and renormalize remaining weights."""
    if not rows: return rows
    def norm(values, value, lower_is_better=False):
        lo, hi = min(values), max(values)
        score = 1.0 if hi == lo else (float(value)-lo)/(hi-lo)
        return 1-score if lower_is_better else score
    price_values=[float(r["total"]) for r in rows]
    fee_values=[float(r["item"].restaurant.delivery_fee) for r in rows]
    speed_values=[r["item"].restaurant.prep_minutes for r in rows]
    portion_values=[r["portion"] for r in rows if r["portion"] is not None]
    for row in rows:
        item=row["item"]
        features={"affordability": norm(price_values,row["total"],True), "rating": (float(item.restaurant.rating)-1)/4, "delivery": norm(fee_values,item.restaurant.delivery_fee,True), "speed": norm(speed_values,item.restaurant.prep_minutes,True)}
        if row["portion"] is not None: features["portion"]=norm(portion_values,row["portion"])
        weight_sum=sum(FOODWISE_WEIGHTS[k] for k in features)
        row["score"]=round(sum(FOODWISE_WEIGHTS[k]*v for k,v in features.items())/weight_sum*100)
        row["score_basis"]=", ".join(features.keys())
    rows.sort(key=lambda x:x["score"],reverse=True)
    return rows

def assign_rider(order):
    """Assign an available demo rider with shortest simulated arrival; lock row to avoid conflicts."""
    candidates = Rider.objects.select_for_update().filter(is_available=True).exclude(assignments__order__status__in=["placed", "accepted", "preparing", "ready", "rider_assigned", "picked_up", "out_for_delivery"]).order_by("travel_minutes")
    rider = candidates.first()
    if rider:
        RiderAssignment.objects.create(order=order, rider=rider)
        order.status = "rider_assigned"
        order.save(update_fields=["status"])
    return rider

def eta_for(order):
    now = timezone.now()
    prep_done = order.ready_at or max(now, order.created_at + timedelta(minutes=order.prep_minutes))
    assignment = getattr(order, "rider_assignment", None)
    rider_arrival = assignment.assigned_at + timedelta(minutes=assignment.rider.travel_minutes) if assignment else now + timedelta(minutes=12)
    pickup = max(prep_done, rider_arrival)
    delivery_minutes = 18
    expected = pickup + timedelta(minutes=delivery_minutes)
    # Provisional fixed buffer: no historical calibration claimed.
    uncertainty = 10 if order.status in ["placed", "accepted", "preparing"] else 6
    return {"low": expected - timedelta(minutes=uncertainty), "high": expected + timedelta(minutes=uncertainty), "expected": expected, "confidence": "Provisional", "factors": [f"Preparation: {order.prep_minutes} min estimate", f"Rider approach: {max(0, int((rider_arrival-now).total_seconds()/60))} min simulated", f"Delivery leg: {delivery_minutes} min demo estimate"]}
