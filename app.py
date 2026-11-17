import pandas as pd
import plotly.graph_objects as go
import dash_ag_grid as dag
from flask import send_from_directory
from dash import Dash, dcc, html, Input, Output, State, callback, clientside_callback, ClientsideFunction, ctx, no_update


COUNTIES= ["Lake","Tehama","Mariposa","Siskiyou"]
VIEWS = {"Lake": (39.13, -122.74, 8.8), "Tehama": (40.12,-122.19, 8.5), "Mariposa": (37.55, -119.86, 9.2), "Siskiyou": (41.50, -122.57, 8.0)}  #lat, lon, zoom
BLUE, CLOSURE_RED, FIRE_COLOR,INK,BORDER = "#1f3a93", "#c62828","#e8a33d","#1a1a1a","#686868"
POP_RAMP = [(1, "#85b8de"), (5, "#4a90c8"), (25,"#1c5fa3"), (100, "#0b2f66")]
FONT= "Times New Roman"
MAPLIBRE = "https://unpkg.com/maplibre-gl@5.24.1/dist/maplibre-gl"  #5.x still ships a plain script build, 6.x is modules only


stations= {}
solutions = {}

for county in COUNTIES:
    stations[county]= pd.read_csv(f"data/{county.lower()}/stations.csv")
    solutions[county] = pd.read_csv(f"data/{county.lower()}/solutions.csv",keep_default_na=False)


def map_data(county, solution):
    closed = stations[county].label.isin(solution["closed"].split(", "))
    lat, lon, zoom = VIEWS[county]
    return {"county": county.lower(), "center": [lon, lat], "zoom": zoom, "ramp": POP_RAMP, "colors": {"wildfire": FIRE_COLOR, "border": BORDER},
            "stations": stations[county].assign(closed=closed)[["label", "station", "lon", "lat", "closed"]].to_dict("records")}


def front_plot(county, solution):
    rows = solutions[county][solutions[county].p ==solution["p"]]
    front= rows[rows.id != "observed"]
    observed = rows[rows.id == "observed"]
    hover = "%{customdata[0]}<br>%{x:,.0f} residents (%{customdata[1]:.1f}%)<br>%{y:.2f} min<extra></extra>"
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=front.Z1, y=front.Z2, customdata=front[["id","Z1_pct"]], hovertemplate=hover, mode="markers",
                                marker={"size": 10, "color": BLUE, "line": {"width": 2, "color": "white"}}, name="Pareto optimal"))

    if len(observed)> 0:  # the observed closures only exist at today's p
        figure.add_trace(go.Scatter(x=observed.Z1, y=observed.Z2, customdata=observed[["id", "Z1_pct"]], hovertemplate=hover, mode="markers",
            marker={"symbol": "star", "size": 18, "color": CLOSURE_RED, "line": {"width": 1,"color": INK}}, name="Observed closures"))
    figure.add_trace(go.Scatter(x=[solution["Z1"]], y=[solution["Z2"]], hoverinfo="skip", mode = "markers",
                                marker={"size": 22, "color": "rgba(0,0,0,0)", "line": {"width": 2, "color": INK}}, name="On the map"))

    figure.update_layout(template="simple_white", font={"family": FONT, "size": 14}, legend={"orientation": "h", "y": 1.14},
                         margin={"l": 60, "r": 10, "t": 30,"b": 50})
    figure.update_xaxes(title="Residents covered (Z1)", showgrid=True, gridcolor="#eeeeee")
    figure.update_yaxes(title="Mean drive time to wildfire, min (Z2)",showgrid=True, gridcolor="#eeeeee", tickformat=".1f")
    return figure



columns = [
    {"field": "id", "headerName": "Solution ID", "flex": 1},
    {"field": "Z1", "headerName": "Residents (Z1)","flex": 1,
     "valueFormatter": {"function": "d3.format(',.0f')(params.value) + ' (' + d3.format('.1f')(params.data.Z1_pct) + '%)'"}},
    {"field": "Z2", "headerName": "Minutes (Z2)", "flex":1, "valueFormatter": {"function": "d3.format('.2f')(params.value)"}},
]

basemaps = [
    {"label": "Light", "value": "light"},
    {"label": "Streets","value": "streets"},
    {"label": "Satellite", "value": "satellite"},
]
ramp_labels = [str(count) for count, color in POP_RAMP]
ramp_labels[-1] += "+"
ramp = html.Span([
    html.Span(style={"display": "block", "height": "10px", "background": "linear-gradient(to right, " + ", ".join(color for count, color in POP_RAMP) + ")"}),
    html.Span([html.Span(label) for label in ramp_labels], style={"display": "flex", "justifyContent": "space-between", "fontSize": "13px"}),
], style={"display": "block", "width": "150px", "margin": "2px 0 4px 22px"})  # scale sits under the residents per cell item

layer_options = [
    {"label": html.Span([html.Span(" ■ ", style={"color": POP_RAMP[2][1]}), "Residents per cell", ramp]), "value": "population"},
    {"label": html.Span([html.Span(" □ ", style={"color": FIRE_COLOR, "fontWeight": "bold"}),"Wildfire cells"]), "value": "wildfire"},
    {"label": html.Span([html.Span(" ● ", style={"color": INK}), "Open stations"]), "value":"open"},
    {"label": html.Span([html.Span(" ✕ ", style={"color": CLOSURE_RED, "fontWeight": "bold"}), "Closed stations"]), "value": "closed"},
    {"label": html.Span([html.Span(" — ", style={"color": BORDER, "fontWeight": "bold"}), "County border"]), "value": "border"},
]

app = Dash(__name__, title="Fire station closures", external_scripts=[MAPLIBRE + ".js"], external_stylesheets=[MAPLIBRE + ".css"])
server= app.server  # entry point for gunicorn on Railway

table_options = {"rowSelection": {"mode": "singleRow", "checkboxes": True, "enableClickSelection": True},  # select box on the far left, or click the row
                 "suppressCellFocus": True,  # no outline box around a clicked cell
                 "theme": {"function": f"themeQuartz.withParams({{fontFamily: '{FONT}', fontSize: 15}})"}}
legend_style = {"position": "absolute", "top": "10px", "left": "10px","zIndex": "1",
                "padding": "6px 10px", "background": "rgba(255,255,255,0.9)", "fontSize": "15px"}


@server.route("/data/<path:path>")
def data_file(path):
    return send_from_directory("data", path)  # the browser fetches each county's cells and border from here


app.layout = html.Div([
    html.Div([
        html.H2("Fire station closures", style={"margin": "0 0 10px"}),
        html.Div([
            html.Div([html.Label("County"), dcc.Dropdown(id="county", options=COUNTIES, value="Lake", clearable=False)], style={"width": "130px"}),
            html.Div([html.Label("Stations open (p)"), dcc.Dropdown(id="p",clearable=False)], style={"width": "130px"}),
            html.Div([html.Label("Basemap"),
                      dcc.Dropdown(id="basemap", options=basemaps, value="light", clearable=False)], style={"width": "160px"}),
        ], style={"display": "flex", "gap": "16px", "marginBottom": "10px"}),

        dag.AgGrid(id="table", columnDefs=columns, getRowId="params.data.id", dashGridOptions=table_options,
                   style={"flex": "1", "minHeight": "150px"}),  # the table takes all the height the front leaves
        dcc.Graph(id="front", style={"height": "300px", "flex": "none"}, config={"displayModeBar":False}),
    ], style={"display": "flex", "flexDirection": "column", "width": "40%", "minWidth": "480px", "padding": "16px", "boxSizing": "border-box"}),

    html.Div([
        dcc.Checklist(id="layers", options=layer_options, value=["population", "wildfire", "open", "closed","border"],
                      labelStyle={"display": "block"}, style=legend_style),
        html.Div(id="map", style={"height": "100%", "--ink": INK, "--closed": CLOSURE_RED}),  # station colors for assets/style.css
        dcc.Store(id="map_data"), dcc.Store(id="drawn"),
    ], style={"flex": "1", "position": "relative"}),
], style={"display": "flex", "position": "fixed", "inset": "0", "fontFamily": FONT})  # fixed to the window, so the page never scrolls


@callback(Output("p", "options"), Output("p", "value"), Input("county", "value"))
def p_choices(county):
    county_solutions = solutions[county]
    observed_p= county_solutions.p[county_solutions.id == "observed"].iloc[0]
    return sorted(county_solutions.p.unique().tolist()),int(observed_p)

@callback(Output("table", "rowData"), Output("table", "selectedRows"),
          Input("county", "value"), Input("p", "value"), Input("front", "clickData"))
def table_rows(county, p, click):
    county_solutions= solutions[county]
    rows = county_solutions[county_solutions.p ==p]
    if ctx.triggered_id=="front":  # a point on the front selects its row
        clicked = click["points"][0]["customdata"][0]
        return no_update, rows[rows.id == clicked].to_dict("records")

    return rows.to_dict("records"), rows.head(1).to_dict("records")  #a new county or p starts on its first row


@callback(Output("map_data", "data"), Output("front", "figure"), Input("table", "selectedRows"), State("county", "value"))
def show_solution(selected_rows, county):
    if not selected_rows:  # unticking the box keeps the last plan on the map
        return no_update, no_update
    county_solutions = solutions[county]
    solution = county_solutions[county_solutions.id == selected_rows[0]["id"]].iloc[0]
    return map_data(county, solution), front_plot(county,solution)


clientside_callback(ClientsideFunction(namespace="maplibre", function_name="draw"), Output("drawn", "data"),
                    Input("map_data", "data"), Input("layers", "value"), Input("basemap", "value"))  # assets/map.js draws the map


if __name__ == "__main__":
    app.run()
