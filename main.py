import wikipediaapi
import networkx as nx
from flask import Flask, request, jsonify, make_response

G = nx.Graph()
wiki = wikipediaapi.Wikipedia('en')


def smaller_graph(pages):
    links = pages.links
    for title in sorted(links.keys()):
        G.add_edge(pages.title, title, weight=1)


def build_graph(pages, start_page, end_page):
    links = pages.links
    for title in sorted(links.keys()):
        G.add_edge(pages.title, title, weight=1)
    while True:
        for title in sorted(links.keys()):
            try:
                k = nx.shortest_path(G, start_page, end_page, weight='weight')
                return k
            except Exception:
                smaller_graph(wiki.page(title))


def sm_graph(page):
    links = page.links
    for title in sorted(links.keys())[0:10]:
        G.add_node(title, size=20, title=(wiki.page(title)).summary[0:60])
        G.add_edge(page.title, title, weight=1)
        link1 = wiki.page(title).links
        for t in sorted(link1.keys())[0:10]:
            G.add_edges_from([(title, t)])
    return G.edges


app = Flask(__name__)


@app.route("/getPath", methods=['POST'])
def shortest_path():
    start_page = request.json['start']
    end_page = request.json['end']
    start = wiki.page(start_page)
    end = wiki.page(end_page)
    if (start.exists()) and (end.exists()):
        payload = {
            "error": False,
            "graph": build_graph(start, start_page, end_page),
            "message": 'A shortest path was found',
            "code": 200

        }
        return make_response(jsonify(payload), 200)
    else:
        payload = {
            "error": True,
            "message": "No such page exists",
            "code": 404
        }
        return make_response(jsonify(payload), 404)


@app.route("/explore", methods=['POST'])
def explore():
    start_page = request.json['start']
    start = wiki.page(start_page)
    if start.exists():
        graph = sm_graph(start)
        payload = {
            "error": False,
            "graph": list(graph),
            "message": 'Here is the path',
            "code": "200"
        }
        return make_response(jsonify(payload), 200)
    else:
        payload = {
            "error": True,
            "message": "No such page exists",
            "code": 404
        }
        return make_response(jsonify(payload), 404)
