import logging
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import requests
from app.cache import get_links_from_cache, set_links_in_cache
import networkx as nx

log = logging.getLogger(__name__)

# Define a session for connection pooling
SESSION = requests.Session()


def get_links_in_bulk(page_titles: list) -> dict:
    """
    Fetches links for a list of pages using efficient bulk API requests,
    while still reading from and writing to the cache on a per-page basis.
    """
    results = {}
    uncached_titles = []

    # 1. First, check the cache for each page
    for title in page_titles:
        cached_links = get_links_from_cache(f"forward_links:{title}")
        if cached_links is not None:
            results[title] = cached_links
        else:
            uncached_titles.append(title)

    if not uncached_titles:
        return results

    # 2. Group the remaining uncached titles into batches of 50
    batches = [uncached_titles[i : i + 50] for i in range(0, len(uncached_titles), 50)]

    # 3. Fetch each batch in parallel
    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(lambda batch: process_batch(batch, results), batches))

    return results


def process_batch(batch: list, results: dict):
    """Processes a single batch of up to 50 titles using prop=links."""
    titles_param = "|".join(batch)
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "titles": titles_param,
        "prop": "links",  # Ask for links directly
        "pllimit": "max",  # Get the maximum number of links
        "redirects": 1,
    }

    try:
        response = SESSION.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json().get("query", {})
    except requests.RequestException as e:
        log.error(f"API request failed for batch starting with '{batch[0]}': {e}")
        return

    # Handle redirects and normalization to map results back to original titles
    redirect_map = {item["from"]: item["to"] for item in data.get("redirects", [])}
    normalized_map = {item["from"]: item["to"] for item in data.get("normalized", [])}

    # Parse the bulk response for links
    for page_id, page_data in data.get("pages", {}).items():
        title = page_data.get("title")
        if not title or "missing" in page_data:
            continue

        # Extract link titles from the 'links' property in the response
        links = page_data.get("links", [])
        article_links = [link["title"] for link in links if ":" not in link["title"]]

        # Cache the result for this specific page
        set_links_in_cache(f"forward_links:{title}", article_links)

        # Add to the results dictionary under its final title
        results[title] = article_links

        # Also map the result back to any original titles that were redirected or normalized
        for original_title, final_title in redirect_map.items():
            if final_title == title:
                results[original_title] = article_links
        for original_title, final_title in normalized_map.items():
            if final_title == title:
                results[original_title] = article_links


def find_shortest_path(start_page, end_page):
    """
    Finds the shortest path using a BFS that fetches links in efficient, parallel batches.
    """
    log.info(f"🚀 Starting BULK search from '{start_page}' to '{end_page}'")
    if start_page == end_page:
        return [start_page]

    level_queue = deque([[start_page]])
    visited = {start_page}

    while level_queue:
        nodes_at_this_level = [path[-1] for path in level_queue]
        log.info(f"--- Exploring level with {len(nodes_at_this_level)} nodes ---")

        bulk_results = get_links_in_bulk(nodes_at_this_level)

        new_paths_for_next_level = deque()

        for _ in range(len(level_queue)):
            current_path = level_queue.popleft()
            current_page = current_path[-1]

            links = bulk_results.get(current_page, [])

            for link in links:
                if link not in visited:
                    visited.add(link)
                    new_path = list(current_path) + [link]

                    if link == end_page:
                        log.info(f"🎉 Path found! Length: {len(new_path)}")
                        return new_path

                    new_paths_for_next_level.append(new_path)

        if not new_paths_for_next_level:
            break

        level_queue = new_paths_for_next_level

    log.warning("Search finished: Path not found.")
    return ["Path not found"]


def generate_explore_graph(start_page):
    """Generates a graph for the explore feature."""
    G = nx.Graph()
    G.add_node(start_page)
    links = get_links_in_bulk([start_page]).get(start_page, [])[:10]

    for link in links:
        G.add_node(link)
        G.add_edge(start_page, link)

    return list(G.nodes), list(G.edges)
