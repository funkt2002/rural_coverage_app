import os
import glob
import pandas as pd
import geopandas as gpd

COUNTIES = ["Lake","Tehama", "Mariposa", "Siskiyou"]
DATA = r"/Users/theofunk/Desktop/Funk_NARSC_2026/data"
SOLUTIONS= r"/Users/theofunk/Desktop/Funk_NARSC_2026/outputs"
OUT = r"/Users/theofunk/Desktop/Funk_NARSC_2026/rural_coverage_app/data"


def station_points(county):
    stations= gpd.read_file(fr"{DATA}/{county.lower()}/stations/stations_model.shp").to_crs(4326)
    return pd.DataFrame({"site_id": stations.site_id, "label": stations.label,"station": stations.station,
                         "open": stations.Open, "lon": stations.geometry.x, "lat":stations.geometry.y})

def demand_cells(county):
    demand= gpd.read_file(fr"{DATA}/{county.lower()}/demand/demand_land.shp")
    routes= pd.read_csv(fr"{DATA}/{county.lower()}/travel_times/d_ij.csv")

    demand= demand.loc[(demand.pop_night>= 1) |(demand.wildfires >= 1)]
    d= routes.pivot(index="cell", columns="site_id",values="minutes")
    return demand.loc[demand.cell.isin(d.dropna().index)].reset_index(drop=True)


def county_boundary(county):
    boundary= gpd.read_file(fr"{DATA}/{county.lower()}/boundaries/boundary.shp")
    return boundary[["geometry"]].to_crs(4326)  


def solution_table(county, stations, residents):
    observed = pd.read_excel(fr"{SOLUTIONS}/{county.lower()}/solutions/observed.xlsx")
    fronts = [pd.read_excel(path) for path in glob.glob(fr"{SOLUTIONS}/{county.lower()}/solutions/pareto_front_*.xlsx")]
    front = pd.concat([observed.head(0)]+ fronts).sort_values(["p", "Z1"]).reset_index(drop=True)
    front["id"]= "par_p" + front.p.astype(str) +"_" + front.groupby("p").cumcount().astype(str) 

    solutions = pd.concat([observed, front],ignore_index=True)
    closed = []
    for sited in solutions[stations.site_id].to_numpy(): 
        closed.append(", ".join(stations.label[sited ==0]))
    solutions["closed"] = closed
    solutions["Z1_pct"] = 100*solutions.Z1 / residents
    return solutions[["id", "p", "Z1", "Z1_pct","Z2", "closed"]]



def main():
    for county in COUNTIES:
        stations= station_points(county)
        demand= demand_cells(county)
        cells= demand[["cell", "pop_night", "wildfires", "geometry"]].to_crs(4326)  
        boundary= county_boundary(county)
        residents= cells.pop_night[cells.pop_night >=1].sum()
        solutions= solution_table(county, stations, residents)
        open_stations= (stations.open == 1).sum()
        wildfires =cells.wildfires.sum()
        closed_now= ", ".join(stations.label[stations.open == 0])
        print(county, ":", len(stations), "stations,", open_stations, "open,",len(cells), "demand cells,",round(residents), "residents,", wildfires, "wildfires,", len(solutions), "solutions")
        print("closed in stations_model.shp:", closed_now)
        print("  closed in observed.xlsx:",solutions.closed[0])
        out = fr"{OUT}/{county.lower()}"
        os.makedirs(out, exist_ok=True)

        stations.to_csv(fr"{out}/stations.csv",index=False)
        cells.to_file(fr"{out}/cells.geojson",driver="GeoJSON", COORDINATE_PRECISION=6) 
        boundary.to_file(fr"{out}/boundary.geojson",driver="GeoJSON")
        solutions.to_csv(fr"{out}/solutions.csv", index= False)
    print("tables ->", OUT)


if __name__ == "__main__":
    main()
