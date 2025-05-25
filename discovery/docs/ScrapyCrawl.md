# 1. Create & activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Make an output directory
mkdir -p output

# 4. Run each spider:

# QuickSpider: ultra-fast HEAD checks
scrapy crawl quick \
  -a start_urls="https://example.com,https://httpbin.org" \
  -o output/quick.json

# StatusSpider: GET requests + metadata extraction
scrapy crawl status \
  -a start_urls="https://example.com,https://httpbin.org" \
  -o output/status.json

# MultiSpider: multi-page crawl with JS rendering
scrapy crawl multi \
  -a start_urls="https://example.com" \
  -a max_depth=2 \
  -o output/multi.json

# SEOSpider: performance & security metrics
scrapy crawl seo \
  -a start_urls="https://example.com" \
  -a max_depth=2 \
  -o output/seo.json

# VisualSpider: visual sitemap (screenshots + graph data)
scrapy crawl visual \
  -a start_urls="https://example.com" \
  -a take_screenshots=True \
  -a extract_visuals=True \
  -a capture_mobile=False \
  -o output/visual.json

# 5. Inspect your results
ls -lh output/*.json
