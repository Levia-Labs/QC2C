# Stage 2
1. copy stage 1 results
2. simplify polygons with removal of unnecessary points: 
if area of polygon with removed point covers the same area as original or more, and it does not intersect with any other,
keep it - basically make local convex hull

`Total runtime: ~800 seconds`
