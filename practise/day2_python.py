store = "12"
product = "Amul butter"
old_price = 52.5
new_price = 55.0
old_units = 40
new_units = 36


print(f"Store {store} raised {product} price from ₹{old_price} to ₹{new_price} (+{(new_price-old_price)*100/old_price:.1f}%)")
print(f"Units fell from {old_units} to {new_units} (-{(old_units-new_units)*100/old_units:.1f}%)")