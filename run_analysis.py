#!/usr/bin/env python3
"""
ARIA: Flood Risk Assessment for Emergency Shelters in Taiwan
"""

import os
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import json
from shapely.geometry import Point
from urllib.parse import quote
import warnings
warnings.filterwarnings('ignore')

# Configuration
CRS_TARGET = 'EPSG:3826'
BUFFER_HIGH = 500
BUFFER_MED = 1000  
BUFFER_LOW = 2000

def main():
    print("ARIA: Flood Risk Assessment for Emergency Shelters in Taiwan")
    print("=" * 60)
    
    # Load river data
    print("Loading river data...")
    rivers_file = 'data/riverpoly/riverpoly.shp'
    if os.path.exists(rivers_file):
        rivers = gpd.read_file(rivers_file)
        print(f"River data loaded: {len(rivers)} features")
    else:
        print("River file not found, loading from API...")
        rivers_url = 'https://gic.wra.gov.tw/Gis/gic/API/Google/DownLoad.aspx?fname=RIVERPOLY&filetype=SHP'
        rivers = gpd.read_file(rivers_url)
    
    rivers = rivers.to_crs(CRS_TARGET)
    
    # Load shelter data
    print("Loading shelter data...")
    shelter_file = 'data/避難收容處所點位檔案v9.csv'
    
    try:
        shelters_csv = pd.read_csv(shelter_file, encoding='utf-8')
        print(f"Shelter CSV loaded: {len(shelters_csv)} records")
    except:
        shelters_csv = pd.read_csv(shelter_file, encoding='big5')
        print(f"Shelter CSV loaded with Big5: {len(shelters_csv)} records")
    
    # Clean shelter data
    lon_col = '經度'
    lat_col = '緯度'
    capacity_col = '預計收容人數'
    
    # Remove invalid coordinates
    valid_coords = (
        shelters_csv[lon_col].notna() & 
        shelters_csv[lat_col].notna() &
        (shelters_csv[lon_col] != 0) & 
        (shelters_csv[lat_col] != 0) &
        (shelters_csv[lon_col] >= 119) & 
        (shelters_csv[lon_col] <= 122) &
        (shelters_csv[lat_col] >= 21) & 
        (shelters_csv[lat_col] <= 26)
    )
    
    shelters_clean = shelters_csv[valid_coords].copy()
    print(f"Valid coordinates: {len(shelters_clean)} shelters")
    
    # Create GeoDataFrame
    shelters = gpd.GeoDataFrame(
        shelters_clean,
        geometry=gpd.points_from_xy(shelters_clean[lon_col], shelters_clean[lat_col]),
        crs='EPSG:4326'
    ).to_crs(CRS_TARGET)
    
    shelters['capacity'] = pd.to_numeric(shelters_clean[capacity_col], errors='coerce').fillna(0).astype(int)
    shelters['shelter_id'] = range(len(shelters))
    
    # Create buffers
    print("Creating buffer zones...")
    buffer_high_list = rivers.buffer(BUFFER_HIGH)
    buffer_med_list = rivers.buffer(BUFFER_MED)
    buffer_low_list = rivers.buffer(BUFFER_LOW)
    
    buffer_high_union = buffer_high_list.unary_union
    buffer_med_union = buffer_med_list.unary_union
    buffer_low_union = buffer_low_list.unary_union
    
    buffers_high = gpd.GeoDataFrame(
        {'risk_level': ['high'], 'distance_m': [BUFFER_HIGH]},
        geometry=[buffer_high_union],
        crs=CRS_TARGET
    )
    
    buffers_med = gpd.GeoDataFrame(
        {'risk_level': ['medium'], 'distance_m': [BUFFER_MED]},
        geometry=[buffer_med_union],
        crs=CRS_TARGET
    )
    
    buffers_low = gpd.GeoDataFrame(
        {'risk_level': ['low'], 'distance_m': [BUFFER_LOW]},
        geometry=[buffer_low_union],
        crs=CRS_TARGET
    )
    
    print(f"High risk buffer: {buffers_high.geometry.iloc[0].area/1000000:.1f} km2")
    print(f"Medium risk buffer: {buffers_med.geometry.iloc[0].area/1000000:.1f} km2")
    print(f"Low risk buffer: {buffers_low.geometry.iloc[0].area/1000000:.1f} km2")
    
    # Assign risk levels
    print("Assigning risk levels...")
    shelters['risk_level'] = 'safe'
    
    high_risk_shelters = gpd.sjoin(shelters, buffers_high, how='inner', predicate='within')
    shelters.loc[high_risk_shelters.index, 'risk_level'] = 'high'
    print(f"High risk shelters: {len(high_risk_shelters)}")
    
    med_risk_shelters = gpd.sjoin(shelters, buffers_med, how='inner', predicate='within')
    med_risk_shelters = med_risk_shelters[~med_risk_shelters.index.isin(high_risk_shelters.index)]
    shelters.loc[med_risk_shelters.index, 'risk_level'] = 'medium'
    print(f"Medium risk shelters: {len(med_risk_shelters)}")
    
    low_risk_shelters = gpd.sjoin(shelters, buffers_low, how='inner', predicate='within')
    low_risk_shelters = low_risk_shelters[~low_risk_shelters.index.isin(high_risk_shelters.index)]
    low_risk_shelters = low_risk_shelters[~low_risk_shelters.index.isin(med_risk_shelters.index)]
    shelters.loc[low_risk_shelters.index, 'risk_level'] = 'low'
    print(f"Low risk shelters: {len(low_risk_shelters)}")
    
    # Risk level summary
    risk_summary = shelters['risk_level'].value_counts()
    print(f"\nRisk level distribution:")
    for level, count in risk_summary.items():
        percentage = (count / len(shelters)) * 100
        print(f"  {level.capitalize()}: {count} shelters ({percentage:.1f}%)")
    
    # Load townships
    print("Loading township boundaries...")
    township_url = 'https://www.tgos.tw/tgos/VirtualDir/Product/3fe61d4a-ca23-4f45-8aca-4a536f40f290/' + quote('鄉(鎮、市、區)界線1140318.zip')
    
    try:
        townships = gpd.read_file(township_url, layer='TOWN_MOI_1140318')
        townships = townships.to_crs(CRS_TARGET)
        print(f"Township data loaded: {len(townships)} townships")
    except Exception as e:
        print(f"Error loading townships: {e}")
        return
    
    # Township analysis
    print("Performing township-level analysis...")
    township_col = 'TOWNID'
    
    shelters_with_township = gpd.sjoin(
        shelters[['shelter_id', 'capacity', 'risk_level', 'geometry']], 
        townships[[township_col, 'geometry']], 
        how='left', 
        predicate='within'
    )
    
    grouped = shelters_with_township.groupby([township_col, 'risk_level']).agg(
        shelter_count=('shelter_id', 'count'),
        total_capacity=('capacity', 'sum')
    ).unstack(fill_value=0)
    
    grouped.columns = [f"{col[0]}_{col[1]}" if col[1] else col[0] for col in grouped.columns]
    township_summary = grouped.reset_index()
    
    # Ensure all expected columns exist
    expected_shelter_cols = ['shelter_count_high', 'shelter_count_medium', 'shelter_count_low', 'shelter_count_safe']
    expected_capacity_cols = ['total_capacity_high', 'total_capacity_medium', 'total_capacity_low', 'total_capacity_safe']
    
    for col in expected_shelter_cols + expected_capacity_cols:
        if col not in township_summary.columns:
            township_summary[col] = 0
    
    township_summary['total_shelters'] = township_summary[expected_shelter_cols].sum(axis=1)
    township_summary['total_capacity'] = township_summary[expected_capacity_cols].sum(axis=1)
    township_summary['risk_capacity_ratio'] = (
        township_summary['total_capacity_high'] + township_summary['total_capacity_medium']
    ) / township_summary['total_capacity'].replace(0, 1)
    
    top_risk_townships = township_summary.sort_values('risk_capacity_ratio', ascending=False).head(10)
    
    print(f"\nTop 10 Most At-Risk Townships:")
    print(top_risk_townships[[
        township_col, 'shelter_count_high', 'shelter_count_safe', 
        'total_capacity_high', 'total_capacity_safe', 'risk_capacity_ratio'
    ]].to_string(index=False))
    
    # Export shelter audit
    print("Exporting shelter risk audit...")
    audit_data = []
    for _, shelter in shelters.iterrows():
        audit_record = {
            'shelter_id': int(shelter['shelter_id']),
            'name': shelter.get('避難收容處所名稱', f'Shelter_{shelter["shelter_id"]}'),
            'risk_level': shelter['risk_level'],
            'capacity': int(shelter['capacity']),
            'longitude': float(shelter.geometry.x),
            'latitude': float(shelter.geometry.y),
            'address': shelter.get('避難收容處所地址', 'Unknown'),
            'county': shelter.get('縣市及鄉鎮市區', 'Unknown')
        }
        audit_data.append(audit_record)
    
    with open('shelter_risk_audit.json', 'w', encoding='utf-8') as f:
        json.dump(audit_data, f, ensure_ascii=False, indent=2)
    
    print(f"Shelter risk audit exported: {len(audit_data)} shelters")
    
    # Create simple visualization
    print("Creating risk map...")
    fig, ax = plt.subplots(1, 1, figsize=(12, 10))
    
    # Plot townships
    townships.plot(ax=ax, facecolor='lightgray', edgecolor='white', linewidth=0.5, alpha=0.7)
    
    # Plot buffer zones
    buffers_low.plot(ax=ax, facecolor='yellow', alpha=0.2, label='Low Risk (2km)')
    buffers_med.plot(ax=ax, facecolor='orange', alpha=0.3, label='Medium Risk (1km)')
    buffers_high.plot(ax=ax, facecolor='red', alpha=0.4, label='High Risk (500m)')
    
    # Plot shelters by risk level
    risk_colors = {'high': 'red', 'medium': 'orange', 'low': 'gold', 'safe': 'green'}
    for risk_level, color in risk_colors.items():
        risk_shelters = shelters[shelters['risk_level'] == risk_level]
        if not risk_shelters.empty:
            risk_shelters.plot(ax=ax, color=color, markersize=3, alpha=0.7, label=f'{risk_level.capitalize()} Risk')
    
    ax.legend(loc='upper left', fontsize=8)
    ax.set_title('Taiwan Flood Risk Map for Emergency Shelters', fontsize=14, fontweight='bold')
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('risk_map.png', dpi=300, bbox_inches='tight')
    print("Risk map saved as 'risk_map.png'")
    
    print("\nAnalysis Complete!")
    print("Files generated:")
    print("  - shelter_risk_audit.json")
    print("  - risk_map.png")

if __name__ == "__main__":
    main()
