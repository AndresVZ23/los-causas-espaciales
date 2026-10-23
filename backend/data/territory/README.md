# Peru COD-AB web assets

Derived from **Peru - Subnational Administrative Boundaries (COD-AB) v01**, source Instituto Geográfico Nacional del Perú (IGN), published by OCHA/HDX under **CC BY-IGO**.

- Canonical dataset: <https://data.humdata.org/dataset/cod-ab-per>
- Pinned source and per-file hashes: `manifest.json`
- Rebuild: `python scripts/data/build_peru_territory.py`
- CRS: GeoJSON CRS84 / EPSG:4326 longitude-latitude
- Role: simplified web reference for search, selection and display

The source boundaries were created in 2015. Districts created later are absent. These assets are not cadastral and must not be used as a substitute for an updated legal delimitation. Simplification is performed in metres and adaptively reduced until the geodesic area change of each feature is at most 1%; shared borders may still exhibit small visual mismatches.
