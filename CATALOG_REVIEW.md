# Catalogue import review

Source: the product table supplied for UGMSA Mini Mart. 88 products in `backend/data/ugmsa_catalog.csv`.
Names and prices are exactly as supplied. Where quantity was blank, stock is **not tracked** (no number invented).

## Please confirm these (imported as written, not changed)
**Possible duplicates**
- `Brown sugar` (Breakfast foods, GH₵15.00, no quantity) and `Brown Sugar` (Staples, GH₵15.00, qty 7).
- `Blue Band Margarine` (GH₵1.00, qty 223) and `Blue band margerine` (GH₵1.00, no category, no quantity). I filed the second under Breakfast.

**Prices of GH₵1.00 that may be placeholders:** Blue Band Margarine, Blue band margerine, Breakfast Cereal, Breakfast Chocolate, Brown Envelope.

**Missing availability:** `Malta Guinness` (GH₵10.00) had no Available value and no quantity. It is imported as **unavailable** until you confirm.

**Possible typos left as written:** `Bet T-roll(Echo)`, `Bet T-roll(perfumed)` (maybe "Bel"), `Mom’s margic sardine`, `Anthena beauty`, `Lifebouy`, `So kiln powder`, `Blue band margerine`, `Can Coke/Fanta/` (trailing slash).

**Category fixes I applied (names untouched):** "Dairy & Foods" for `Eggs(Half-crate)` treated as Dairy & Eggs. "Beverage/Beverages" merged into Drinks. Soap and Toothpaste go to Toiletries, Tissue paper to Household, Fast foods to Noodles, Sardines to Canned, `Avivar Sausage` to a new Frozen & Chilled category.

**Not grouped as variants:** Coca-cola (small/medium/1 litre), Indomie (3 sizes) and the eggs are separate products with their exact names. Variants are supported if you want them grouped.

**Large or odd quantities:** Bic Pen 325, Blue Band Margarine 223, Bourbon Biscuit Big 117. Basmati Rice is GH₵480.00 with qty 1.

The sample Orders row (Milo 1kg Tin, GH₵195) is not in the product list, so it was not imported.
