# Sigiriya Tour Guide Map

A Flutter app featuring an interactive map of Sigiriya Rock Fortress with 8 points of interest (POIs). Users can explore historical locations, view descriptions, and receive proximity notifications when nearby.

## Features
- Interactive Google Map with real-time user location
- 8 points of interest with descriptions:
  - Water Fountains
  - Water Garden
  - Sigiriya Entrance
  - Bridge over Moat
  - Summer Palace
  - Caves with Inscriptions
  - Lion's Paw
  - Main Palace
- Proximity-based notifications (300m trigger radius)
- Marker clustering and animated camera transitions
- Drawer-based POI details with distance calculation
- Live location tracking with accuracy visualization

## Getting Started

Prerequisites:
- Flutter SDK installed and on PATH
- Android/iOS device or emulator with location services
- Google Maps API key (Android & iOS)

### Google Maps Setup

#### Android
1. Get a Google Maps API key from [Google Cloud Console](https://console.cloud.google.com/)
2. Edit `android/app/src/main/AndroidManifest.xml` and add:
```xml
<meta-data
    android:name="com.google.android.geo.API_KEY"
    android:value="YOUR_API_KEY_HERE"/>
```

#### iOS
1. Get a Google Maps API key from [Google Cloud Console](https://console.cloud.google.com/)
2. Edit `ios/Runner/GeneratedPluginRegistrant.m` and add your API key (or configure in Podfile)
3. Add to `ios/Runner/Info.plist`:
```xml
<key>GoogleMapsApiKey</key>
<string>YOUR_API_KEY_HERE</string>
```

### Run the app

```bash
cd sigiriya_tour_guide
flutter pub get
flutter run
```



## How It Works

1. **Map View**: Shows your real-time location (blue dot) with a 300m detection radius (blue circle)
2. **POI Markers**: Red markers show all 8 Sigiriya attractions
3. **Proximity Alerts**: When you enter 300m of a POI, a notification dialog appears
4. **Drawer Details**: Click a marker or tap "View Details" to open a drawer with:
   - Distance from your location
   - Full historical description
   - "View on Map" button to animate camera to that POI
5. **POI List**: "Nearby Sites" FAB shows a sorted list of all attractions with distances

## Customization

- **Trigger radius**: Edit `triggerRadiusMeters` in `lib/main.dart` (line 120)
- **Add more POIs**: Extend the `sigiriyaPOIs` list in `lib/main.dart` with new `PointOfInterest` objects
- **Map styling**: Customize colors in the GoogleMap widget or use custom map styles

## File Structure

- `lib/main.dart` – Main app logic with POI data model and map integration
- `android/app/src/main/AndroidManifest.xml` – Android permissions and Google Maps key
- `ios/Runner/Info.plist` – iOS permissions and Google Maps key
- `pubspec.yaml` – Dependencies (geolocator, google_maps_flutter)
