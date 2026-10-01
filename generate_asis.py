#!/usr/bin/env python3
"""BPMN AS-IS: контроль участка цеха ЧКПЗ по видеонаблюдению."""
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent
X0, COL_W = 250, 210
TASK_W, TASK_H, GW, EV = 170, 78, 50, 36
C_OP = ("#D4E7FF", "#1A5FB4")
C_SHOP = ("#D6F5D6", "#2E7D32")
C_SYS = ("#EBD9FB", "#7B2CBF")
C_GW = ("#FFF3BF", "#B08900")
C_ST = ("#C9F2CD", "#1B5E20")
C_EN = ("#FFD2D2", "#B71C1C")

POOL_X, POOL_Y = 140, 40
SYS_Y, SYS_H = 40, 200
OP_Y, OP_H = 240, 400
SHOP_Y, SHOP_H = 640, 180
SYS_C, OP_A, OP_B, SHOP_C = 130, 340, 500, 730


def el(tag, attrs=None, text=None, children=None):
    attrs = attrs or {}
    attr_s = "".join(f' {k}="{escape(str(v))}"' for k, v in attrs.items())
    if children:
        return f"<{tag}{attr_s}>\n" + "\n".join(children) + f"\n</{tag}>"
    if text is not None:
        return f"<{tag}{attr_s}>{escape(text)}</{tag}>"
    return f"<{tag}{attr_s} />"


class Layout:
    def __init__(self):
        self.geo = {}
        self.shapes = []
        self.edges = []
        self.artifacts = []
        self.data_elems = []

    def place(self, eid, col, cy, w, h, fill=None, stroke=None):
        x = X0 + col * COL_W + (COL_W - w) / 2
        y = cy - h / 2
        self.geo[eid] = (x, y, w, h)
        attrs = {"id": f"{eid}_di", "bpmnElement": eid}
        if stroke:
            attrs["bioc:stroke"] = stroke
            attrs["color:border-color"] = stroke
        if fill:
            attrs["bioc:fill"] = fill
            attrs["color:background-color"] = fill
        self.shapes.append(el("bpmndi:BPMNShape", attrs, children=[
            el("dc:Bounds", {"x": round(x), "y": round(y), "width": w, "height": h})
        ]))

    def lane(self, eid, y, h, fill):
        self.shapes.append(el("bpmndi:BPMNShape", {
            "id": f"{eid}_di", "bpmnElement": eid, "isHorizontal": "true",
            "bioc:fill": fill, "color:background-color": fill,
        }, children=[el("dc:Bounds", {
            "x": POOL_X + 30, "y": y, "width": 2060, "height": h,
        })]))

    def pool(self, eid):
        self.shapes.insert(0, el("bpmndi:BPMNShape", {
            "id": f"{eid}_di", "bpmnElement": eid, "isHorizontal": "true",
        }, children=[el("dc:Bounds", {
            "x": POOL_X, "y": POOL_Y, "width": 2090, "height": 780,
        })]))

    def edge(self, fid, pts):
        wps = [el("di:waypoint", {"x": round(x), "y": round(y)}) for x, y in pts]
        self.edges.append(el("bpmndi:BPMNEdge", {"id": f"{fid}_di", "bpmnElement": fid}, children=wps))

    def mid_right(self, eid):
        x, y, w, h = self.geo[eid]
        return x + w, y + h / 2

    def mid_left(self, eid):
        x, y, w, h = self.geo[eid]
        return x, y + h / 2

    def mid_top(self, eid):
        x, y, w, h = self.geo[eid]
        return x + w / 2, y

    def mid_bot(self, eid):
        x, y, w, h = self.geo[eid]
        return x + w / 2, y + h

    def forward(self, fid, src, tgt):
        x1, y1 = self.mid_right(src)
        x2, y2 = self.mid_left(tgt)
        if abs(y1 - y2) < 2:
            self.edge(fid, [(x1, y1), (x2, y2)])
        else:
            mx = (x1 + x2) / 2
            self.edge(fid, [(x1, y1), (mx, y1), (mx, y2), (x2, y2)])

    def down(self, fid, src, tgt):
        x1, y1 = self.mid_bot(src)
        x2, y2 = self.mid_top(tgt)
        if abs(x1 - x2) < 2:
            self.edge(fid, [(x1, y1), (x2, y2)])
        else:
            self.edge(fid, [(x1, y1), (x1, (y1 + y2) / 2), (x2, (y1 + y2) / 2), (x2, y2)])

    def store(self, eid, name, col, cy):
        self.data_elems.append(el("dataStoreReference", {"id": eid, "name": name}))
        self.place(eid, col, cy, 56, 50, None, "#7B2CBF")

    def data(self, eid, name, col, cy):
        self.data_elems.append(el("dataObject", {"id": f"Obj_{eid}"}))
        self.data_elems.append(el("dataObjectReference", {
            "id": eid, "name": name, "dataObjectRef": f"Obj_{eid}",
        }))
        self.place(eid, col, cy, 36, 50, None, "#555555")

    def dotted(self, fid, src, tgt):
        self.artifacts.append(el("association", {
            "id": fid, "associationDirection": "One",
            "sourceRef": src, "targetRef": tgt,
        }))
        x1, y1 = self.mid_bot(src)
        x2, y2 = self.mid_top(tgt)
        self.edge(fid, [(x1, y1), (x2, y2)])


def build():
    L = Layout()
    items = [
        ("Start", "startEvent", "Началась смена поста", 0, OP_A, EV, EV, C_ST),
        ("T1", "serviceTask", "Показать поток на пост и писать архив", 1, SYS_C, TASK_W, TASK_H, C_SYS),
        ("T2", "userTask", "Смотреть экраны", 2, OP_A, TASK_W, TASK_H, C_OP),
        ("G1", "exclusiveGateway", "Нарушение видно на экране?", 3, OP_A, GW, GW, C_GW),
        ("T3", "userTask", "Внести замеченный факт в электронный журнал", 4, OP_B, TASK_W, TASK_H, C_OP),
        ("T4", "manualTask", "Сообщить ответственному цеха", 5, OP_B, TASK_W, TASK_H, C_OP),
        ("T5", "manualTask", "Принять решение по ситуации", 6, SHOP_C, TASK_W, TASK_H, C_SHOP),
        ("G2", "exclusiveGateway", "Смена закончена?", 7, OP_A, GW, GW, C_GW),
        ("End", "endEvent", "Смена закрыта", 8, OP_A, EV, EV, C_EN),
    ]
    for eid, _, _, col, cy, w, h, color in items:
        L.place(eid, col, cy, w, h, *color)
    L.store("DS_Archive", "Архив видеонаблюдения", 1.38, 195)
    L.data("DO_Journal", "Электронный журнал", 4.42, 590)

    L.lane("Lane_Sys", SYS_Y, SYS_H, "#F9F3FE")
    L.lane("Lane_Op", OP_Y, OP_H, "#F3F8FF")
    L.lane("Lane_Shop", SHOP_Y, SHOP_H, "#F4FBF4")
    L.pool("Participant")

    flows = [
        ("F1", "Start", "T1", None),
        ("F2", "T1", "T2", None),
        ("F3", "T2", "G1", None),
        ("F4", "G1", "T3", "Видно"),
        ("F5", "T3", "T4", None),
        ("F6", "T4", "T5", None),
        ("F7", "T5", "G2", None),
        ("F8", "G1", "G2", "Не видно"),
        ("F9", "G2", "End", "Да"),
        ("F10", "G2", "T2", "Смена идёт"),
    ]
    for fid, src, tgt, _ in flows:
        if fid == "F8":
            L.forward(fid, src, tgt)
        elif fid == "F10":
            x1, y1 = L.mid_top("G2")
            x2, y2 = L.mid_top("T2")
            bus = 268
            L.edge(fid, [(x1, y1), (x1, bus), (x2, bus), (x2, y2)])
        elif fid in ("F4", "F6"):
            L.down(fid, src, tgt)
        elif fid == "F7":
            x1, y1 = L.mid_top("T5")
            x2, y2 = L.mid_bot("G2")
            L.edge(fid, [(x1, y1), (x1, (y1 + y2) / 2), (x2, (y1 + y2) / 2), (x2, y2)])
        else:
            L.forward(fid, src, tgt)
    L.dotted("DA1", "T1", "DS_Archive")
    L.dotted("DA2", "T3", "DO_Journal")

    nodes = [el(tag, {"id": eid, "name": name}) for eid, tag, name, *_ in items]
    fl = []
    for fid, src, tgt, name in flows:
        a = {"id": fid, "sourceRef": src, "targetRef": tgt}
        if name:
            a["name"] = name
        fl.append(el("sequenceFlow", a))

    lanes = el("laneSet", {"id": "LaneSet"}, children=[
        el("lane", {"id": "Lane_Sys", "name": "Система видеонаблюдения"}, children=[
            el("flowNodeRef", text="T1")]),
        el("lane", {"id": "Lane_Op", "name": "Оператор видеонаблюдения"}, children=[
            el("flowNodeRef", text=r) for r in ("Start", "T2", "G1", "T3", "T4", "G2", "End")]),
        el("lane", {"id": "Lane_Shop", "name": "Ответственный цеха"}, children=[
            el("flowNodeRef", text="T5")]),
    ])
    process = el("process", {
        "id": "Process_ASIS", "name": "Контроль участка по видеонаблюдению",
        "isExecutable": "false",
    }, children=[lanes, *nodes, *L.data_elems, *fl, *L.artifacts])
    collab = el("collaboration", {"id": "Collaboration_ASIS"}, children=[
        el("participant", {
            "id": "Participant",
            "name": "AS-IS: контроль участка цеха человеком по видеонаблюдению",
            "processRef": "Process_ASIS",
        })])
    diagram = el("bpmndi:BPMNDiagram", {"id": "BPMNDiagram_ASIS"}, children=[
        el("bpmndi:BPMNPlane", {"id": "BPMNPlane_ASIS", "bpmnElement": "Collaboration_ASIS"},
           children=[*L.shapes, *L.edges])])
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"
             xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
             xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
             xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
             xmlns:bioc="http://bpmn.io/schema/bpmn/biocolor/1.0"
             xmlns:color="http://www.omg.org/spec/BPMN/non-normative/color/1.0"
             xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
             id="Definitions_ASIS"
             targetNamespace="http://local/bpmn/video"
             exporter="generate_asis.py" exporterVersion="1.0">
{collab}
{process}
{diagram}
</definitions>
"""
    path = OUT / "AS-IS_videonablyudenie.bpmn"
    path.write_text(xml, encoding="utf-8")
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>AS-IS: видеонаблюдение ЧКПЗ</title>
<script src="https://unpkg.com/bpmn-js@17.11.1/dist/bpmn-navigated-viewer.production.min.js"></script>
<style>
  html, body {{ margin: 0; height: 100%; font-family: -apple-system, sans-serif; }}
  #canvas {{ width: 100%; height: 100%; }}
  h3 {{ position: absolute; z-index: 10; margin: 8px 14px; color: #333; }}
</style>
</head>
<body>
<h3>AS-IS: контроль участка цеха человеком по видеонаблюдению</h3>
<div id="canvas"></div>
<script type="text/xml" id="bpmn-xml">{xml}</script>
<script>
  const viewer = new BpmnJS({{ container: '#canvas' }});
  viewer.importXML(document.getElementById('bpmn-xml').textContent).then(() => {{
    viewer.get('canvas').zoom('fit-viewport');
    document.title = 'READY';
  }}).catch(err => {{ document.title = 'ERROR'; console.error(err); }});
</script>
</body>
</html>
"""
    (OUT / "preview_asis.html").write_text(html, encoding="utf-8")
    print(path)


if __name__ == "__main__":
    build()
