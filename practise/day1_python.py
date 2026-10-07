




product_name="Amul butter"
store="12"
last_week =120
this_week = 72
price_per_unit = 52.5
drop_in_units= last_week - this_week
week_revenue= this_week * price_per_unit
print (last_week, this_week, price_per_unit, drop_in_units, week_revenue)
drop_pct = drop_in_units / last_week
print("Store : %s" % store)
print ("Product : %s" % product_name)
print (f"Units : last week :%d, this week : %d" % (last_week, this_week))
print ("Drop in units : %i, drop_pct: %.2f" % (drop_in_units, drop_pct))
print ("week revenue : $%.2f" % week_revenue)

