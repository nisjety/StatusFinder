# discovery/spiders/visual_spider.py

import logging
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse
from collections import defaultdict
import json

import scrapy
from scrapy import signals
from scrapy.http import Request
from scrapy.exceptions import DontCloseSpider
from scrapy_playwright.page import PageMethod

from discovery.items import VisualItem
from discovery.spiders.seo_spider import SEOSpider


class VisualSpider(SEOSpider):
    name = 'visual'
    custom_settings = {
        'HTTPCACHE_ENABLED': False,
        # We'll inject DEPTH_LIMIT in __init__
    }

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        # Disconnect the parent's spider_idle handler to avoid conflicts
        try:
            crawler.signals.disconnect(spider._on_spider_idle, signal=signals.spider_idle)
        except Exception:
            pass
        # Connect our own spider_idle handler
        crawler.signals.connect(spider._on_visual_spider_idle, signal=signals.spider_idle)
        return spider

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.name)

        # — parse start_urls & allowed_domains —
        raw = kwargs.get('start_urls') or getattr(self, 'start_urls', [])
        if isinstance(raw, str):
            self.start_urls = [u.strip() for u in raw.split(',') if u.strip()]
        else:
            self.start_urls = list(raw)

        if not getattr(self, 'allowed_domains', None):
            self.allowed_domains = [urlparse(u).netloc for u in self.start_urls]

        # — feature flags - properly parse boolean values —
        def parse_bool(value):
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ('true', '1', 'yes', 'on')
            return bool(value)

        self.extract_visuals = parse_bool(kwargs.get('extract_visuals', True))
        self.generate_sitemap = parse_bool(kwargs.get('generate_sitemap', True))

        # — depth —
        self.max_depth = int(kwargs.get('max_depth', 1))
        self.max_depth_seen = 0

        # enforce DEPTH_LIMIT
        self.custom_settings['DEPTH_LIMIT'] = self.max_depth

        # Sitemap data structure
        self.sitemap_data = {
            'nodes': {},  # url -> node data
            'edges': [],  # list of {source, target} links
            'root_urls': list(self.start_urls)
        }
        
        # Track pending requests to know when to generate summary
        self.pending_requests = set()
        self.processed_urls = set()
        self._stats_generated = False

        self.logger.info(
            f"VisualSpider(start_urls={self.start_urls}, "
            f"allowed_domains={self.allowed_domains}, "
            f"extract_visuals={self.extract_visuals}, "
            f"generate_sitemap={self.generate_sitemap}, "
            f"max_depth={self.max_depth})"
        )

    def _on_visual_spider_idle(self, spider):
        """Called when spider goes idle - generate summary stats if not done yet."""
        if not self._stats_generated and not self.pending_requests:
            self._stats_generated = True
            summary_item = dict(self.generate_summary_stats())
            summary_item['item_type'] = 'summary_statistics'
            
            # Schedule a dummy request to yield the summary
            req = Request(
                url=self.start_urls[0] + '#summary',
                callback=self._yield_summary,
                dont_filter=True,
                priority=100
            )
            req.meta['summary_item'] = summary_item
            self.crawler.engine.crawl(req)
            raise DontCloseSpider()
    
    def _yield_summary(self, response):
        """Yield the summary statistics item."""
        yield response.meta['summary_item']

    def start_requests(self):
        for url in self.start_urls:
            self.logger.info(f"Scheduling root URL: {url}")
            self.pending_requests.add(url)
            yield Request(
                url=url,
                callback=self.parse,
                errback=self.error_callback,
                meta={
                    'depth': 0,
                    'parent_url': None,
                    'playwright': self.extract_visuals,  # Only use Playwright if extracting visuals
                    'playwright_include_page': self.extract_visuals,
                    'playwright_page_methods': [
                        PageMethod('wait_for_load_state', 'networkidle'),
                    ] if self.extract_visuals else [],
                },
            )

    async def parse(self, response):
        depth = response.meta['depth']
        parent = response.meta['parent_url']
        page = response.meta.get('playwright_page') if self.extract_visuals else None

        self.logger.info(f"Processing {response.url} at depth {depth}")
        self.max_depth_seen = max(self.max_depth_seen, depth)
        
        # Mark URL as processed
        self.processed_urls.add(response.url)

        # Add to sitemap data
        if self.generate_sitemap:
            self._add_to_sitemap(response.url, parent, depth)

        # build the item
        item = VisualItem()
        item['url'] = response.url
        item['parent_url'] = parent
        item['depth'] = depth
        item['status_code'] = response.status
        item['timestamp'] = datetime.now().isoformat()
        item['metadata'] = {}

        # basic page info
        item['title'] = response.css('title::text').get(default='')
        item['headings'] = response.css('h1::text, h2::text, h3::text').getall()

        # nav links
        nav = response.css('nav a::attr(href)').getall()
        item['nav_links'] = [urljoin(response.url, h) for h in nav]

        # images
        imgs = response.css('img')
        item['images'] = [
            {'src': urljoin(response.url, img.attrib.get('src', '')),
             'alt': img.attrib.get('alt', '')}
            for img in imgs
        ]
        item['images_count'] = len(item['images'])

        # No screenshots - removed functionality
        item['screenshot'] = None

        # visual-element extraction
        if page and self.extract_visuals:
            try:
                item['visual_data'] = await self._extract_visual_elements(page)
            except Exception:
                self.logger.exception("Visual extraction failed")
                item['visual_data'] = {'error': 'visual-extraction-failed'}
        else:
            item['visual_data'] = {}

        # embed the inherited SEO analysis
        item['seo_data'] = self._analyze_seo(response)

        yield item

        # follow **unique**, internal http(s) links up to max_depth
        if depth < self.max_depth:
            seen_hrefs = set()
            all_links = response.css('a::attr(href)').getall()
            
            for href in all_links:
                # strip fragments & whitespace
                href = href.split('#', 1)[0].strip()
                if not href or href in seen_hrefs:
                    continue
                seen_hrefs.add(href)

                abs_url = urljoin(response.url, href)
                p = urlparse(abs_url)
                if p.scheme not in ('http', 'https'):
                    continue
                if not any(p.netloc == d or p.netloc.endswith(f".{d}")
                           for d in self.allowed_domains):
                    continue

                # Skip if already processed or pending
                if abs_url in self.processed_urls or abs_url in self.pending_requests:
                    continue

                # Add edge to sitemap
                if self.generate_sitemap:
                    self.sitemap_data['edges'].append({
                        'source': response.url,
                        'target': abs_url,
                        'depth': depth
                    })

                self.logger.info(f"Following link to {abs_url} (depth {depth + 1})")
                self.pending_requests.add(abs_url)
                
                yield Request(
                    url=abs_url,
                    callback=self.parse,
                    errback=self.error_callback,
                    meta={
                        'depth': depth + 1,
                        'parent_url': response.url,
                        'playwright': self.extract_visuals,
                        'playwright_include_page': self.extract_visuals,
                        'playwright_page_methods': [
                            PageMethod('wait_for_load_state', 'networkidle'),
                        ] if self.extract_visuals else [],
                    },
                )
        
        # Remove from pending
        self.pending_requests.discard(response.url)

    def _add_to_sitemap(self, url: str, parent_url: str, depth: int):
        """Add a URL to the sitemap data structure."""
        if url not in self.sitemap_data['nodes']:
            self.sitemap_data['nodes'][url] = {
                'url': url,
                'parent': parent_url,
                'depth': depth,
                'children': [],
                'timestamp': datetime.now().isoformat()
            }
        
        # Add child relationship
        if parent_url and parent_url in self.sitemap_data['nodes']:
            if url not in self.sitemap_data['nodes'][parent_url]['children']:
                self.sitemap_data['nodes'][parent_url]['children'].append(url)

    async def _extract_visual_elements(self, page) -> dict:
        data = {}
        try:
            data['dominant_colors'] = await page.evaluate("""
                () => {
                    const counts = {};
                    for (const el of document.querySelectorAll('*')) {
                        const s = getComputedStyle(el);
                        [s.backgroundColor, s.color].forEach(c => {
                            if (c && c!=='transparent') counts[c] = (counts[c]||0)+1;
                        });
                    }
                    return Object.entries(counts)
                                 .sort((a,b)=>b[1]-a[1])
                                 .slice(0,10);
                }
            """)
            data['dimensions'] = await page.evaluate("""
                () => ({
                    viewport:{w:window.innerWidth,h:window.innerHeight},
                    page:{w:document.documentElement.scrollWidth,
                          h:document.documentElement.scrollHeight}
                })
            """)
            data['fonts'] = await page.evaluate("""
                () => {
                    const fc={};
                    for (const el of document.querySelectorAll('*')) {
                        const f = getComputedStyle(el).fontFamily;
                        if (f) fc[f]=(fc[f]||0)+1;
                    }
                    return Object.entries(fc)
                                 .sort((a,b)=>b[1]-a[1])
                                 .slice(0,5);
                }
            """)
            data['layout'] = await page.evaluate("""
                () => {
                    const out=[];
                    ['header','nav','main','footer','aside','section','article']
                      .forEach(sel=>document.querySelectorAll(sel)
                        .forEach(el=>{
                          const r=el.getBoundingClientRect();
                          out.push({type:sel,rect:r.toJSON()});
                        }));
                    return out;
                }
            """)
            data['interactive_elements'] = await page.evaluate("""
                () => {
                    const elems=[];
                    document.querySelectorAll('button,input,select,textarea,[onclick],[role="button"]').forEach(el=>{
                        const r=el.getBoundingClientRect();
                        if(r.width>0&&r.height>0){
                            elems.push({
                              tag:el.tagName.toLowerCase(),
                              type:el.type||'',
                              text:el.textContent.trim().slice(0,50),
                              rect:r.toJSON()
                            });
                        }
                    });
                    return elems;
                }
            """)
        except Exception:
            self.logger.exception("Error extracting visual elements")
            data['error'] = 'visual-extraction-failed'
        return data

    def error_callback(self, failure):
        req = failure.request
        self.logger.error(f"Request failed: {req.url} → {failure.value}")
        
        # Remove from pending
        self.pending_requests.discard(req.url)
        
        yield {
            'url': req.url,
            'status_code': -1,
            'timestamp': datetime.now().isoformat(),
            'error': str(failure.value),
        }

    def closed(self, reason):
        super().closed(reason)
        self.logger.info(f"Max depth reached: {self.max_depth_seen}")
        
        # Save sitemap data if enabled
        if self.generate_sitemap and self.sitemap_data['nodes']:
            try:
                # Create a hierarchical sitemap structure
                sitemap = self._create_hierarchical_sitemap()
                
                # Save sitemap to file
                import os
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                sitemap_dir = os.path.join('data', 'sitemaps')
                os.makedirs(sitemap_dir, exist_ok=True)
                
                sitemap_file = os.path.join(sitemap_dir, f'sitemap_{self.name}_{timestamp}.json')
                with open(sitemap_file, 'w', encoding='utf-8') as f:
                    json.dump(sitemap, f, indent=2)
                
                self.logger.info(f"Sitemap saved to: {sitemap_file}")
                
                # Also save a D3.js compatible format
                d3_data = self._create_d3_sitemap()
                d3_file = os.path.join(sitemap_dir, f'd3_sitemap_{self.name}_{timestamp}.json')
                with open(d3_file, 'w', encoding='utf-8') as f:
                    json.dump(d3_data, f, indent=2)
                
                self.logger.info(f"D3.js sitemap saved to: {d3_file}")
                
                # Save HTML visualization
                html_file = os.path.join(sitemap_dir, f'sitemap_viz_{self.name}_{timestamp}.html')
                # Make the JSON path relative to the HTML file
                relative_json_path = os.path.basename(d3_file)
                with open(html_file, 'w', encoding='utf-8') as f:
                    f.write(self._generate_sitemap_html(relative_json_path))
                
                self.logger.info(f"HTML visualization saved to: {html_file}")
                
            except Exception as e:
                self.logger.error(f"Failed to save sitemap: {e}")
        
        if hasattr(self.crawler, 'stats'):
            self.crawler.stats.set_value('visual_spider/max_depth', self.max_depth_seen)
            self.crawler.stats.set_value('visual_spider/total_urls', len(self.sitemap_data['nodes']))

    def _create_hierarchical_sitemap(self) -> dict:
        """Create a hierarchical representation of the sitemap."""
        # Build tree structure
        tree = {
            'url': 'root',
            'children': []
        }
        
        # Group URLs by depth
        urls_by_depth = defaultdict(list)
        for url, data in self.sitemap_data['nodes'].items():
            urls_by_depth[data['depth']].append(url)
        
        # Create nodes for root URLs
        for root_url in self.start_urls:
            if root_url in self.sitemap_data['nodes']:
                node = self._build_tree_node(root_url)
                tree['children'].append(node)
        
        return {
            'tree': tree,
            'total_urls': len(self.sitemap_data['nodes']),
            'max_depth': self.max_depth_seen,
            'edges': self.sitemap_data['edges']
        }
    
    def _build_tree_node(self, url: str) -> dict:
        """Recursively build a tree node for a URL."""
        node_data = self.sitemap_data['nodes'].get(url, {})
        node = {
            'url': url,
            'depth': node_data.get('depth', 0),
            'children': []
        }
        
        # Add children recursively
        for child_url in node_data.get('children', []):
            if child_url in self.sitemap_data['nodes']:
                child_node = self._build_tree_node(child_url)
                node['children'].append(child_node)
        
        return node
    
    def _create_d3_sitemap(self) -> dict:
        """Create D3.js compatible data for force-directed graph."""
        nodes = []
        links = []
        
        # Create nodes with proper IDs
        for idx, (url, data) in enumerate(self.sitemap_data['nodes'].items()):
            nodes.append({
                'id': url,
                'name': urlparse(url).path or '/',
                'depth': data['depth'],
                'group': data['depth']  # Group by depth for coloring
            })
        
        # Create links
        for edge in self.sitemap_data['edges']:
            links.append({
                'source': edge['source'],
                'target': edge['target'],
                'value': 1
            })
        
        return {
            'nodes': nodes,
            'links': links
        }
    
    def _generate_sitemap_html(self, json_filename: str) -> str:
        """Generate HTML visualization for the sitemap."""
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>Site Map Visualization</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }}
        #visualization {{
            width: 100%;
            height: 800px;
            background: white;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        .node {{
            cursor: pointer;
        }}
        .node circle {{
            stroke: #fff;
            stroke-width: 2px;
        }}
        .node text {{
            font-size: 12px;
            pointer-events: none;
        }}
        .link {{
            fill: none;
            stroke: #999;
            stroke-opacity: 0.6;
            stroke-width: 1px;
        }}
        .tooltip {{
            position: absolute;
            text-align: left;
            padding: 10px;
            font: 12px sans-serif;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            border-radius: 4px;
            pointer-events: none;
            opacity: 0;
        }}
        h1 {{
            color: #333;
        }}
        .info {{
            margin-bottom: 20px;
            color: #666;
        }}
    </style>
</head>
<body>
    <h1>Site Map Visualization</h1>
    <div class="info">
        <p>Interactive force-directed graph of the website structure. 
        Drag nodes to reorganize, hover for details.</p>
    </div>
    <div id="visualization"></div>
    
    <script>
        // Load the data
        d3.json('{json_filename}').then(function(data) {{
            const width = document.getElementById('visualization').clientWidth;
            const height = 800;
            
            // Create SVG
            const svg = d3.select('#visualization')
                .append('svg')
                .attr('width', width)
                .attr('height', height);
            
            // Create tooltip
            const tooltip = d3.select('body').append('div')
                .attr('class', 'tooltip');
            
            // Color scale
            const color = d3.scaleOrdinal(d3.schemeCategory10);
            
            // Create simulation
            const simulation = d3.forceSimulation(data.nodes)
                .force('link', d3.forceLink(data.links).id(d => d.id).distance(100))
                .force('charge', d3.forceManyBody().strength(-300))
                .force('center', d3.forceCenter(width / 2, height / 2))
                .force('collision', d3.forceCollide().radius(30));
            
            // Create links
            const link = svg.append('g')
                .selectAll('line')
                .data(data.links)
                .enter().append('line')
                .attr('class', 'link');
            
            // Create nodes
            const node = svg.append('g')
                .selectAll('.node')
                .data(data.nodes)
                .enter().append('g')
                .attr('class', 'node')
                .call(d3.drag()
                    .on('start', dragstarted)
                    .on('drag', dragged)
                    .on('end', dragended));
            
            // Add circles to nodes
            node.append('circle')
                .attr('r', d => 10 + (3 - d.depth) * 5)
                .style('fill', d => color(d.group));
            
            // Add labels to nodes
            node.append('text')
                .attr('dx', 12)
                .attr('dy', '.35em')
                .text(d => d.name);
            
            // Add hover effects
            node.on('mouseover', function(event, d) {{
                tooltip.transition().duration(200).style('opacity', .9);
                tooltip.html(`<strong>${{d.id}}</strong><br/>Depth: ${{d.depth}}`)
                    .style('left', (event.pageX + 10) + 'px')
                    .style('top', (event.pageY - 28) + 'px');
            }})
            .on('mouseout', function(d) {{
                tooltip.transition().duration(500).style('opacity', 0);
            }});
            
            // Update positions on tick
            simulation.on('tick', () => {{
                link
                    .attr('x1', d => d.source.x)
                    .attr('y1', d => d.source.y)
                    .attr('x2', d => d.target.x)
                    .attr('y2', d => d.target.y);
                
                node
                    .attr('transform', d => `translate(${{d.x}},${{d.y}})`);
            }});
            
            // Drag functions
            function dragstarted(event, d) {{
                if (!event.active) simulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
            }}
            
            function dragged(event, d) {{
                d.fx = event.x;
                d.fy = event.y;
            }}
            
            function dragended(event, d) {{
                if (!event.active) simulation.alphaTarget(0);
                d.fx = null;
                d.fy = null;
            }}
        }});
    </script>
</body>
</html>"""