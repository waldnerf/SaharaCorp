# Policy: Use the Price Paid, Not the Current Catalog Price

Product prices and costs change over time (`product_pricing` is a
point-in-time history table). When answering any question about revenue,
margin, or "how much a product sold for," always use the price and cost
that were actually in effect at the moment of the transaction — which are
already captured on the order line itself (`order_items.unit_price` and
`order_items.unit_cost`) — never the current catalog price, and never a
value looked up from `product_pricing` for computing historical
transactions.

**Why this matters:** `product_pricing` exists to answer questions that are
specifically *about* price history or today's catalog price (e.g. "what
does this product cost today," "how has the price of X changed over
time"). It is a dimension table, not a transaction fact. Using it to
recompute historical revenue would substitute today's price for the price
a customer actually paid on a given date — silently rewriting history any
time a product's price has changed since the sale.

Sahara Retail changes prices periodically (promotions, cost changes,
seasonal repricing). A product sold in January and again in June may have
two different prices on `product_pricing`, and neither may match what a
customer actually paid if a line-level discount was also applied. The only
source of truth for "what was paid" is the order line.

**Practical rule:** revenue, cost, and margin computations join
`order_items` to `orders` (and `returns`), never to `product_pricing`.
`product_pricing` is only relevant for questions explicitly about price
history or the current catalog, not for computing what happened
transactionally at any point in time. This matches
`semantic/retail.ossie.yaml`'s `order_items` dataset description and the
`product_pricing` dataset's `ai_context`.
