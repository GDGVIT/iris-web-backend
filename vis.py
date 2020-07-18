from pyvis.network import Network
import wikipediaapi
import networkx as nx
import json
from functools import lru_cache

G = nx.Graph()
wiki = wikipediaapi.Wikipedia('en')


@lru_cache()
def sm_graph(page):
    links = page.links
    for title in sorted(links.keys())[0:20]:
        G.add_node(title, size=20, title=(wiki.page(title)).summary[0:60])
        G.add_edge(page.title, title, weight=1)
        link1 = wiki.page(title).links
        for t in sorted(link1.keys())[0:10]:
            G.add_edges_from([(title, t)])
    return G


start_page = "JavaScript"
# end_page = "Italy"

G1 = sm_graph(wiki.page(start_page))
# k = nx.shortest_path(G1, start_page, end_page, weight='weight')
# print(k)
for g in G.nodes:
    # if g in k:
    G.nodes[g]['color'] = "blue"
    G.nodes[g]['size'] = 20
# for i in range(0, len(k) - 1):
#     G[k[i]][k[i + 1]]['color'] = "red"
nt = Network("1080px", "1920px")

nt.from_nx(G1)
nt.show("nx.html")
