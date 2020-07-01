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
