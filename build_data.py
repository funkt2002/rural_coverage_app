import os
import glob
import pandas as pd
import geopandas as gpd

COUNTIES = ["Lake","Tehama", "Mariposa", "Siskiyou"]
DATA = r"/Users/theofunk/Desktop/Funk_NARSC_2026/data"
SOLUTIONS= r"/Users/theofunk/Desktop/Funk_NARSC_2026/outputs"
OUT = r"/Users/theofunk/Desktop/Funk_NARSC_2026/rural_coverage_app/data"


def station_points(county):
    stations= gpd.read_file(fr"{DATA}/{county.lower()}/stations/stations_model.shp").to_crs(4326)  # lon/lat for the web map
    return pd.DataFrame({"site_id": stations.site_id, "label": stations.label,"station": stations.station,
                         "open": stations.Open, "lon": stations.geometry.x, "lat":stations.geometry.y})

def demand_cells(county):
    demand = gpd.read_file(fr"{DATA}/{county.lower()}/demand/demand_land.shp")
    routes = pd.read_csv(fr"{DATA}/{county.lower()}/travel_times/d_ij.csv")

    demand= demand.loc[(demand.pop_night>= 1) |(demand.wildfires >= 1)]
    d = routes.pivot(index="cell", columns="site_id",values="minutes")
    return demand.loc[demand.cell.isin(d.dropna().index)].reset_index(drop=True)  #same cells as station_coverage_model.ipynb


def county_boundary(county):
    boundary = gpd.read_file(fr"{DATA}/{county.lower()}/boundaries/boundary.shp")
    return boundary[["geometry"]].to_crs(4326)  # lon/lat for the web map


def solution_table(county, stations, residents):
    observed = pd.read_excel(fr"{SOLUTIONS}/{county.lower()}/solutions/observed.xlsx")
    fronts = [pd.read_excel(path) for path in glob.glob(fr"{SOLUTIONS}/{county.lower()}/solutions/pareto_front_*.xlsx")]  # only Lake has a front so far
    front = pd.concat([observed.head(0)]+ fronts).sort_values(["p", "Z1"]).reset_index(drop=True)  # head(0) lets a county without a front through
    front["id"]= "par_p" + front.p.astype(str) +"_" + front.groupby("p").cumcount().astype(str)  # same names as the lake_map_par_p15_0 to _14 maps

    solutions = pd.concat([observed, front],ignore_index=True)
    closed = []
    for sited in solutions[stations.site_id].to_numpy():  #one 0/1 column per site_id
        closed.append(", ".join(stations.label[sited ==0]))
    solutions["closed"] = closed
    solutions["Z1_pct"] = 100*solutions.Z1 / residents
    return solutions[["id", "p", "Z1", "Z1_pct","Z2", "closed"]]



def main():
    for county in COUNTIES:
        stations = station_points(county)
        demand = demand_cells(county)
        cells = demand[["cell", "pop_night", "wildfires", "geometry"]].to_crs(4326)  # the 270 m cells in lon/lat for the map
        boundary = county_boundary(county)
        residents = cells.pop_night[cells.pop_night >=1].sum()  # sum of a_i, cells under 1 resident carry no demand in the model
        solutions = solution_table(county, stations, residents)

        open_stations = (stations.open == 1).sum()
        wildfires =cells.wildfires.sum()
        closed_now = ", ".join(stations.label[stations.open == 0])
        print(county, ":", len(stations), "stations,", open_stations, "open,",len(cells), "demand cells,",
              round(residents), "residents,", wildfires, "wildfires,", len(solutions), "solutions")
        print("  closed in stations_model.shp:", closed_now)
        print("  closed in observed.xlsx:     ",solutions.closed[0])
        out = fr"{OUT}/{county.lower()}"
        os.makedirs(out, exist_ok=True)

        stations.to_csv(fr"{out}/stations.csv", index=False)
        cells.to_file(fr"{out}/cells.geojson", driver="GeoJSON", COORDINATE_PRECISION=6)  #6 decimals is about 0.1 m
        boundary.to_file(fr"{out}/boundary.geojson", driver="GeoJSON")
        solutions.to_csv(fr"{out}/solutions.csv", index= False)
    print("tables ->", OUT)


if __name__ == "__main__":
    main()
