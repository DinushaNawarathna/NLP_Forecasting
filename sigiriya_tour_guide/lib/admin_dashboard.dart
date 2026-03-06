import 'dart:convert';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:fl_chart/fl_chart.dart';
import 'admin_login_screen.dart';

class AdminDashboard extends StatefulWidget {
  final Map<String, dynamic> adminData;

  const AdminDashboard({super.key, required this.adminData});

  @override
  State<AdminDashboard> createState() => _AdminDashboardState();
}

class _AdminDashboardState extends State<AdminDashboard> {
  int _selectedIndex = 0;
  Map<String, dynamic> _dashboardStats = {};
  List<dynamic> _weeklyForecast = [];
  List<dynamic> _weatherData = [];
  Map<String, dynamic> _monthlyForecast = {}; // Store monthly data from XGBoost model
  bool _isLoadingStats = true;
  
  // Feature 3: Custom Date Range Selector
  DateTime _selectedStartDate = DateTime(2026, 1, 1);
  DateTime _selectedEndDate = DateTime(2026, 12, 31);
  
  // Facility Capacity
  int _facilityCapacity = 0;
  
  // Alerts Management
  List<Map<String, dynamic>> _alerts = [];
  bool _showAlertPopup = false;
  
  static const String apiBaseUrl = 'http://10.0.2.2:8000';

  @override
  void initState() {
    super.initState();
    _loadAllData();
  }

  Future<void> _loadCapacityFromModels() async {
    try {
      // Get capacity from monthly forecast - find the maximum visitor count
      if (_monthlyForecast.isNotEmpty) {
        final values = _monthlyForecast.values.whereType<int>().toList();
        if (values.isNotEmpty) {
          final maxVisitors = values.reduce((a, b) => a > b ? a : b);
          // Set capacity as 110% of max to provide buffer
          setState(() {
            _facilityCapacity = (maxVisitors * 1.1).toInt();
          });
          print('✓ Capacity from forecast models: $_facilityCapacity');
          return;
        }
      }

      // Fallback: Try API endpoint
      final response = await http.get(
        Uri.parse('$apiBaseUrl/admin/capacity'),
        headers: {
          'Authorization': 'Bearer ${widget.adminData['token']}',
          'Content-Type': 'application/json',
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        try {
          final data = json.decode(response.body);
          if (data is Map && data.containsKey('capacity')) {
            setState(() {
              _facilityCapacity = int.tryParse('${data['capacity']}') ?? 6000;
            });
            print('✓ Capacity from API: $_facilityCapacity');
            return;
          }
        } catch (e) {
          print('Error parsing capacity: $e');
        }
      }
    } catch (e) {
      print('Error loading capacity from models: $e');
    }
    // Default fallback
    setState(() {
      _facilityCapacity = 6000;
    });
    print('✓ Capacity default fallback: $_facilityCapacity');
  }

  Future<void> _loadAllData() async {
    setState(() => _isLoadingStats = true);
    try {
      await Future.wait([
        _loadDashboardStats(),
        _loadForecastData(),
        _loadMonthlyForecast(),
        _loadWeatherData(),
        _loadCapacityFromModels(),
      ]);

      _generateSampleAlerts();

      setState(() => _isLoadingStats = false);

      if (!_showAlertPopup) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          _showInitialAlertPopup();
        });
      }
    } catch (e) {
      print('Error loading all data: $e');
      _generateSampleAlerts();
      setState(() => _isLoadingStats = false);
      // Use default capacity if load fails
      _facilityCapacity = 6000;

      if (!_showAlertPopup) {
        WidgetsBinding.instance.addPostFrameCallback((_) {
          _showInitialAlertPopup();
        });
      }
    }
  }

  int get _unreadAlertsCount => _alerts.where((alert) => alert['isRead'] != true).length;

  IconData _getAlertIcon(Map<String, dynamic> alert) {
    final icon = alert['icon'];
    return icon is IconData ? icon : Icons.notifications_active;
  }

  Color _getAlertColor(Map<String, dynamic> alert) {
    final color = alert['color'];
    return color is Color ? color : Colors.blue;
  }

  void _generateSampleAlerts() {
    if (_weeklyForecast.isEmpty || _weatherData.isEmpty) return;

    final generatedAlerts = <Map<String, dynamic>>[];
    final todayData = _weeklyForecast.first as Map<String, dynamic>?;
    final todayWeather = _weatherData.first as Map<String, dynamic>?;
    final todayVisitors = _getCrowdValue(todayData);

    // Crowd alert: > 1000 visitors
    if (todayVisitors > 1000) {
      generatedAlerts.add({
        'title': 'High Crowd Alert',
        'message': 'Expected visitors: $todayVisitors today. Prepare additional staff.',
        'icon': Icons.people,
        'color': todayVisitors > 1500 ? Colors.red : Colors.orange,
        'isRead': false,
        'type': 'crowd',
      });
    }

    // Capacity alert: > 1500 visitors
    if (todayVisitors > 1500) {
      generatedAlerts.add({
        'title': 'Exceeding Safe Visitor Limit',
        'message': 'Expected visitors ($todayVisitors) exceed safe daily limit (1500). Prepare crowd management and extra staff.',
        'icon': Icons.warning_amber_rounded,
        'color': Colors.red,
        'isRead': false,
        'type': 'capacity',
      });
    }

    if (todayWeather != null) {
      // Parse temperature
      num temp = 0;
      try {
        final tempVal = todayWeather['temperature'];
        temp = tempVal is num ? tempVal : num.tryParse('$tempVal') ?? 0;
      } catch (e) {
        print('Error parsing temp: $e');
      }

      // Parse rainfall
      num rainfall = 0;
      try {
        final rainVal = todayWeather['rainfall'];
        rainfall = rainVal is num ? rainVal : num.tryParse('$rainVal') ?? 0;
      } catch (e) {
        print('Error parsing rainfall: $e');
      }

      // Parse wind speed
      num windSpeed = 0;
      try {
        final windVal = todayWeather['wind_speed'];
        windSpeed = windVal is num ? windVal : num.tryParse('$windVal') ?? 0;
      } catch (e) {
        print('Error parsing wind speed: $e');
      }

      // HEAT Alert: > 24°C
      if (temp > 24) {
        generatedAlerts.add({
          'title': 'HEAT Alert',
          'message': 'Temperature ${temp.toStringAsFixed(1)}°C. Increase water stations and shaded rest areas.',
          'icon': Icons.wb_sunny,
          'color': Colors.deepOrange,
          'isRead': false,
          'type': 'heat',
        });
      }

      // Very High Temperature Alert: > 33°C
      if (temp > 33) {
        generatedAlerts.add({
          'title': 'Extreme Heat Warning',
          'message': 'Temperature ${temp.toStringAsFixed(1)}°C - Critical heat alert. Mandatory staff breaks and hydration.',
          'icon': Icons.thermostat,
          'color': Colors.red,
          'isRead': false,
          'type': 'weather',
        });
      }

      // Rain Alert: > 5mm
      if (rainfall > 5) {
        generatedAlerts.add({
          'title': 'Rain Warning',
          'message': 'Rainfall expected: ${rainfall.toStringAsFixed(1)}mm. Prepare indoor facilities and covered areas.',
          'icon': Icons.cloud_queue,
          'color': Colors.blue,
          'isRead': false,
          'type': 'rain',
        });
      }

      // Heavy Rain Alert: > 50mm
      if (rainfall > 50) {
        generatedAlerts.add({
          'title': 'Heavy Rain Alert',
          'message': 'Heavy rainfall forecasted: ${rainfall.toStringAsFixed(1)}mm. Close outdoor attractions if needed.',
          'icon': Icons.opacity,
          'color': Colors.indigo,
          'isRead': false,
          'type': 'heavyrain',
        });
      }

      // High Wind Alert: > 8 m/s
      if (windSpeed > 8) {
        generatedAlerts.add({
          'title': 'High Wind Warning',
          'message': 'Wind speed: ${windSpeed.toStringAsFixed(1)} m/s. Secure loose items and monitor visitor safety.',
          'icon': Icons.air,
          'color': Colors.amber,
          'isRead': false,
          'type': 'wind',
        });
      }

      // Extreme Wind Alert: > 15 m/s
      if (windSpeed > 15) {
        generatedAlerts.add({
          'title': 'Extreme Wind Alert',
          'message': 'Dangerous wind: ${windSpeed.toStringAsFixed(1)} m/s. Restrict outdoor movement and activities.',
          'icon': Icons.storm,
          'color': Colors.red,
          'isRead': false,
          'type': 'extremewind',
        });
      }
    }

    if (mounted) {
      setState(() {
        _alerts = generatedAlerts;
      });
    }
  }

  void _markAllAlertsAsRead() {
    if (!mounted || _alerts.isEmpty) return;

    setState(() {
      _alerts = _alerts
          .map((alert) => {
                ...alert,
                'isRead': true,
              })
          .toList();
    });
  }

  Future<void> _showInitialAlertPopup() async {
    if (!mounted || _alerts.isEmpty || _showAlertPopup) return;

    _showAlertPopup = true;

    await showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) {
        return AlertDialog(
          titlePadding: const EdgeInsets.fromLTRB(20, 16, 8, 0),
          title: Row(
            children: [
              const Expanded(
                child: Text(
                  'Alerts',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                ),
              ),
              IconButton(
                icon: const Icon(Icons.close, size: 24),
                tooltip: 'Close',
                onPressed: () => Navigator.of(context).pop(),
              ),
            ],
          ),
          contentPadding: const EdgeInsets.fromLTRB(20, 12, 20, 12),
          content: SizedBox(
            width: 400,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: _alerts.map((alert) {
                  final color = _getAlertColor(alert);
                  final icon = _getAlertIcon(alert);
                  return Container(
                    margin: const EdgeInsets.only(bottom: 12),
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: color.withOpacity(0.08),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: color.withOpacity(0.3), width: 1.5),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(icon, color: color, size: 24),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                '${alert['title'] ?? 'Alert'}',
                                style: const TextStyle(
                                  fontWeight: FontWeight.w700,
                                  fontSize: 15,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                '${alert['message'] ?? ''}',
                                style: TextStyle(
                                  fontSize: 13,
                                  color: Colors.grey.shade700,
                                  height: 1.4,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  );
                }).toList(),
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Dismiss'),
            ),
          ],
        );
      },
    );

    _markAllAlertsAsRead();
  }

  Future<void> _showAlertsDialog() async {
    if (!mounted || _alerts.isEmpty) return;

    _markAllAlertsAsRead();

    await showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          titlePadding: const EdgeInsets.fromLTRB(20, 16, 8, 0),
          title: Row(
            children: [
              const Expanded(
                child: Text(
                  'All Alerts',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                ),
              ),
              IconButton(
                icon: const Icon(Icons.close, size: 24),
                tooltip: 'Close',
                onPressed: () => Navigator.of(context).pop(),
              ),
            ],
          ),
          contentPadding: const EdgeInsets.fromLTRB(20, 12, 20, 12),
          content: SizedBox(
            width: 420,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: _alerts.map((alert) {
                  final color = _getAlertColor(alert);
                  final icon = _getAlertIcon(alert);
                  return Container(
                    margin: const EdgeInsets.only(bottom: 12),
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: color.withOpacity(0.08),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: color.withOpacity(0.3), width: 1.5),
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Icon(icon, color: color, size: 24),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                '${alert['title'] ?? 'Alert'}',
                                style: const TextStyle(
                                  fontWeight: FontWeight.w700,
                                  fontSize: 15,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                '${alert['message'] ?? ''}',
                                style: TextStyle(
                                  fontSize: 13,
                                  color: Colors.grey.shade700,
                                  height: 1.4,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  );
                }).toList(),
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildAlertBellAction() {
    return IconButton(
      tooltip: 'Alerts',
      onPressed: _alerts.isEmpty ? null : _showAlertsDialog,
      icon: Stack(
        clipBehavior: Clip.none,
        children: [
          const Icon(Icons.notifications_none, color: Colors.white),
          if (_unreadAlertsCount > 0)
            Positioned(
              right: -8,
              top: -8,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                decoration: BoxDecoration(
                  color: Colors.red,
                  borderRadius: BorderRadius.circular(10),
                ),
                constraints: const BoxConstraints(minWidth: 18, minHeight: 16),
                child: Text(
                  _unreadAlertsCount > 99 ? '99+' : '$_unreadAlertsCount',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  Future<void> _loadDashboardStats() async {
    try {
      final response = await http
          .get(
            Uri.parse('$apiBaseUrl/admin/stats'),
            headers: {
              'Authorization': 'Bearer ${widget.adminData['token']}',
              'Content-Type': 'application/json',
            },
          )
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        setState(() {
          _dashboardStats = json.decode(response.body);
        });
      }
    } catch (e) {
      print('Error loading stats: $e');
    }
  }

  Future<void> _loadForecastData() async {
    try {
      // Try new analytics endpoint first
      final response = await http.get(
        Uri.parse('$apiBaseUrl/admin/daily-analytics?limit=90'),
        headers: {
          'Authorization': 'Bearer ${widget.adminData['token']}',
          'Content-Type': 'application/json',
        },
      ).timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        try {
          final data = json.decode(response.body);
          print('✓ Daily Analytics API Success: ${data.runtimeType}');
          if (data is List && data.isNotEmpty) {
            print('✓ Analytics is List with ${data.length} items');
            print('✓ First item: ${data.first}');
            setState(() {
              _weeklyForecast = data;
            });
            return;
          }
        } catch (e) {
          print('✗ Error parsing daily analytics: $e');
        }
      }
      
      // Fallback to old forecast endpoint
      final fallbackResponse = await http.get(
        Uri.parse('$apiBaseUrl/forecast?limit=90&year=2026'),
        headers: {
          'Authorization': 'Bearer ${widget.adminData['token']}',
          'Content-Type': 'application/json',
        },
      ).timeout(const Duration(seconds: 15));

      if (fallbackResponse.statusCode == 200) {
        try {
          final data = json.decode(fallbackResponse.body);
          print('✓ Forecast API Success: ${data.runtimeType}');
          if (data is List && data.isNotEmpty) {
            print('✓ Forecast is List with ${data.length} items');
            // Convert to dashboard format
            final convertedData = (data as List).map((item) {
              if (item is Map) {
                return {
                  'date': item['date'] ?? '',
                  'day': item['day'] ?? 'Unknown',
                  'visitors': item['forecast_visitor_count'] ?? item['visitors'] ?? 0,
                  'temperature': 28,
                  'crowd_level': 'Moderate'
                };
              }
              return item;
            }).toList();
            print('✓ First converted item: ${convertedData.first}');
            setState(() {
              _weeklyForecast = convertedData;
            });
            return;
          } else if (data is Map && data.containsKey('data')) {
            print('✓ Forecast has data key');
            setState(() {
              _weeklyForecast = data['data'] is List ? data['data'] : [];
            });
            return;
          }
        } catch (e) {
          print('✗ Error parsing forecast: $e');
          print('Raw body: ${fallbackResponse.body.substring(0, min(500, fallbackResponse.body.length))}');
        }
      } else {
        print('✗ Forecast API error: ${fallbackResponse.statusCode}');
      }
    } catch (e) {
      print('✗ Error loading forecast: $e');
    }
    
    // Fallback: Generate synthetic forecast data
    print('⚠ Using synthetic forecast data');
    final syntheticForecast = _generateSyntheticForecast();
    print('✓ Generated ${syntheticForecast.length} synthetic forecast items');
    print('✓ First synthetic item: ${syntheticForecast.first}');
    setState(() {
      _weeklyForecast = syntheticForecast;
    });
  }

  Future<void> _loadMonthlyForecast() async {
    try {
      // Try new monthly analytics endpoint first
      final response = await http.get(
        Uri.parse('$apiBaseUrl/admin/monthly-analytics?year=2026'),
        headers: {
          'Authorization': 'Bearer ${widget.adminData['token']}',
          'Content-Type': 'application/json',
        },
      ).timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        try {
          final data = json.decode(response.body);
          print('✓ Monthly Analytics API Success: ${data.runtimeType}');
          
          if (data is List && data.isNotEmpty) {
            print('✓ Monthly data is List with ${data.length} items');
            print('✓ First item: ${data.first}');
            
            // Convert list to map for easier access by month name
            Map<String, int> monthlyMap = {};
            for (var item in data) {
              if (item is Map) {
                final monthName = item['month'] ?? '';
                final avgVisitors = item['average_visitors'] ?? 0;
                monthlyMap[monthName] = avgVisitors;
                print('✓ Month: $monthName → $avgVisitors visitors');
              }
            }
            
            setState(() {
              _monthlyForecast = monthlyMap;
            });
            print('✓ Monthly forecast loaded with ${monthlyMap.length} months');
            return;
          }
        } catch (e) {
          print('✗ Error parsing monthly analytics: $e');
          print('Raw response: ${response.body.substring(0, min(500, response.body.length))}');
        }
      } else {
        print('✗ Monthly Analytics API error: ${response.statusCode}');
      }
      
      // Fallback: Try old monthly forecast endpoint
      final fallbackResponse = await http.get(
        Uri.parse('$apiBaseUrl/forecast/monthly?year=2026'),
        headers: {
          'Authorization': 'Bearer ${widget.adminData['token']}',
          'Content-Type': 'application/json',
        },
      ).timeout(const Duration(seconds: 15));

      if (fallbackResponse.statusCode == 200) {
        try {
          final data = json.decode(fallbackResponse.body);
          print('✓ Monthly Forecast API Success: ${data.runtimeType}');
          
          if (data is List && data.isNotEmpty) {
            print('✓ Monthly data is List with ${data.length} items');
            
            // Convert list to map
            Map<String, int> monthlyMap = {};
            for (var item in data) {
              if (item is Map) {
                monthlyMap[item['month'] ?? ''] = item['average_visitors'] ?? 0;
              }
            }
            
            setState(() {
              _monthlyForecast = monthlyMap;
            });
            return;
          }
        } catch (e) {
          print('✗ Error parsing forecast/monthly: $e');
        }
      }
    } catch (e) {
      print('✗ Error loading monthly forecast: $e');
    }
    
    // Fallback: Generate synthetic monthly data with variation
    print('⚠ Generating synthetic monthly data with variation');
    final monthNames = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December'
    ];
    final syntheticMonthly = <String, int>{};
    
    // Create varying visitor patterns by month
    for (int i = 0; i < monthNames.length; i++) {
      // Peak seasons: January, July, August, December (holidays)
      int baseVisitors = 3500;
      if ([0, 6, 7, 11].contains(i)) {
        baseVisitors = 4500; // Peak season
      } else if ([1, 11].contains(i)) {
        baseVisitors = 3000; // Low season
      }
      syntheticMonthly[monthNames[i]] = baseVisitors + Random().nextInt(500);
    }
    
    setState(() {
      _monthlyForecast = syntheticMonthly;
    });
    print('✓ Generated synthetic monthly data with varying values');
  }

  List<Map<String, dynamic>> _generateSyntheticForecast() {
    final now = DateTime.now();
    final forecast = <Map<String, dynamic>>[];
    
    for (int i = 0; i < 90; i++) {
      final date = now.add(Duration(days: i));
      final baseVisitors = 3200 + (i % 20) * 150;
      
      forecast.add({
        'date': date.toString().split(' ')[0],
        'visitors': baseVisitors,
        'lower_bound': (baseVisitors * 0.85).toInt(),
        'upper_bound': (baseVisitors * 1.15).toInt(),
      });
    }
    
    return forecast;
  }

  String _formatWeatherValue(dynamic value) {
    if (value == null) return '0.0';
    if (value is num) {
      return value.toStringAsFixed(1);
    } else if (value is String) {
      try {
        return double.parse(value).toStringAsFixed(1);
      } catch (e) {
        return '0.0';
      }
    }
    return '0.0';
  }

  int _getCrowdValue(Map<String, dynamic>? data) {
    if (data == null) return 0;
    try {
      final visitors = data['visitors'];
      if (visitors is int) return visitors;
      if (visitors is num) return visitors.toInt();
      if (visitors is String) return int.parse(visitors);
    } catch (e) {
      print('Error getting crowd value: $e, data: $data');
    }
    return 0;
  }

  int _safeToInt(dynamic value, [int defaultValue = 0]) {
    try {
      if (value is int) return value;
      if (value is double) return value.toInt();
      if (value is num) return value.toInt();
      if (value is String) return int.parse(value);
    } catch (e) {
      print('Error converting to int: $e, value: $value');
    }
    return defaultValue;
  }

  Map<String, int> _getMonthlyAggregates(List<dynamic> forecast) {
    Map<String, int> monthlyData = {};
    final monthNames = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
    ];

    if (forecast.isEmpty) {
      // Return empty months with 0 values if no forecast
      for (int i = 0; i < 12; i++) {
        monthlyData[monthNames[i]] = 0;
      }
      return monthlyData;
    }

    // Initialize all 12 months with 0
    for (int i = 0; i < 12; i++) {
      monthlyData[monthNames[i]] = 0;
    }

    // Group forecast data by month
    Map<int, List<int>> monthVisitors = {};

    for (int i = 0; i < forecast.length; i++) {
      try {
        final visitors = _getCrowdValue(forecast[i]);
        
        // Determine the date (assume forecast starts from today)
        DateTime currentDate = DateTime.now().add(Duration(days: i));
        int monthIndex = currentDate.month - 1;
        
        // Initialize month data if not exists
        if (!monthVisitors.containsKey(monthIndex)) {
          monthVisitors[monthIndex] = [];
        }
        
        monthVisitors[monthIndex]!.add(visitors);
      } catch (e) {
        print('Error processing monthly data: $e');
      }
    }

    // Calculate averages for each month
    for (var entry in monthVisitors.entries) {
      int monthIndex = entry.key;
      List<int> visitors = entry.value;
      int average = 0;
      if (visitors.isNotEmpty) {
        average = (visitors.reduce((a, b) => a + b) / visitors.length).toInt();
      }
      monthlyData[monthNames[monthIndex]] = average;
    }

    return monthlyData;
  }

  Future<void> _loadWeatherData() async {
    try {
      final response = await http.get(
        Uri.parse('$apiBaseUrl/weather_forecast?limit=30'),
        headers: {
          'Authorization': 'Bearer ${widget.adminData['token']}',
          'Content-Type': 'application/json',
        },
      ).timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        try {
          final data = json.decode(response.body);
          print('✓ Weather API Success: ${data.runtimeType}');
          if (data is List && data.isNotEmpty) {
            print('✓ Weather is List with ${data.length} items');
            print('✓ First item: ${data.first}');
            setState(() {
              _weatherData = data;
            });
            return;
          } else if (data is Map && data.containsKey('data')) {
            print('✓ Weather has data key');
            setState(() {
              _weatherData = data['data'] is List ? data['data'] : [];
            });
            return;
          }
        } catch (e) {
          print('✗ Error parsing weather: $e');
          print('Raw body: ${response.body.substring(0, min(500, response.body.length))}');
        }
      } else {
        print('✗ Weather API error: ${response.statusCode}');
      }
    } catch (e) {
      print('✗ Error loading weather: $e');
    }
    
    // Fallback: Generate synthetic weather data
    print('⚠ Using synthetic weather data');
    final syntheticWeather = _generateSyntheticWeather();
    print('✓ Generated ${syntheticWeather.length} synthetic weather items');
    print('✓ First synthetic item: ${syntheticWeather.first}');
    setState(() {
      _weatherData = syntheticWeather;
    });
  }

  List<Map<String, dynamic>> _generateSyntheticWeather() {
    final now = DateTime.now();
    final weather = <Map<String, dynamic>>[];
    final conditions = ['Sunny', 'Partly Cloudy', 'Cloudy', 'Light Rain', 'Rainy'];
    
    for (int i = 0; i < 30; i++) {
      final date = now.add(Duration(days: i));
      final temp = 26.0 + (i % 10) * 1.5 - 4;
      
      weather.add({
        'date': date.toString().split(' ')[0],
        'temperature': temp,
        'rainfall': ((i % 5) * 5).toDouble(),
        'wind_speed': 3.5 + (i % 4) * 1.2,
        'condition': conditions[i % conditions.length],
      });
    }
    
    return weather;
  }

  void _handleLogout() {
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (context) => const AdminLoginScreen(),
      ),
    );
  }

  Future<void> _exportCrowdDataAsCSV() async {
    try {
      if (_weeklyForecast.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('No data available to export')),
        );
        return;
      }

      StringBuffer csv = StringBuffer('Date,Predicted Visitors,Lower Bound,Upper Bound\n');
      
      for (var item in _weeklyForecast) {
        try {
          // Handle various field name formats
          final date = item['date'] ?? item['ds'] ?? '';
          final visitors = item['visitors'] ?? item['yhat'] ?? item['expected_visitors'] ?? 0;
          final visitorsInt = _safeToInt(visitors, 0);
          final lowerBound = item['lower_bound'] ?? item['yhat_lower'] ?? visitorsInt * 0.8 ?? 0;
          final upperBound = item['upper_bound'] ?? item['yhat_upper'] ?? visitorsInt * 1.2 ?? 0;
          
          if (date.toString().isNotEmpty) {
            csv.writeln('$date,${visitors ?? 0},${(lowerBound as num).toStringAsFixed(0)},${(upperBound as num).toStringAsFixed(0)}');
          }
        } catch (e) {
          print('Error parsing item: $e, item: $item');
          continue;
        }
      }

      _showCSVDialog('Crowd Data Export', csv.toString());
    } catch (e) {
      print('Error exporting: $e');
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error exporting data: $e')),
      );
    }
  }

  void _showCSVDialog(String title, String csvContent) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: SingleChildScrollView(
          child: SelectableText(
            csvContent,
            style: const TextStyle(fontSize: 10, fontFamily: 'monospace'),
          ),
        ),
        actions: [
          TextButton.icon(
            onPressed: () {
              Clipboard.setData(ClipboardData(text: csvContent));
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('CSV copied to clipboard')),
              );
              Navigator.pop(context);
            },
            icon: const Icon(Icons.copy),
            label: const Text('Copy'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  Future<void> _exportWeatherDataAsCSV() async {
    try {
      if (_weatherData.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('No data available to export')),
        );
        return;
      }

      StringBuffer csv = StringBuffer('Date,Temperature (°C),Rainfall (mm),Wind Speed (m/s),Condition\n');
      
      for (var item in _weatherData) {
        try {
          final date = item['date'] ?? item['dt'] ?? '';
          final temp = (item['temperature'] ?? item['temp'] ?? 0).toString();
          final rain = (item['rainfall'] ?? item['rain'] ?? 0).toString();
          final wind = (item['wind_speed'] ?? 0).toString();
          final condition = (item['condition'] ?? item['description'] ?? 'N/A').toString();
          
          if (date.toString().isNotEmpty) {
            csv.writeln('$date,$temp,$rain,$wind,$condition');
          }
        } catch (e) {
          print('Error parsing weather item: $e');
          continue;
        }
      }

      _showCSVDialog('Weather Data Export', csv.toString());
    } catch (e) {
      print('Error exporting: $e');
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error exporting data: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final List<Widget> screens = [
      _buildDashboardHome(),
      _buildAnalyticsScreen(),
      _buildSeasonalTrendsScreen(),
      _buildCapacityUtilizationScreen(),
      _buildCustomReportScreen(),
      _buildReportsScreen(),
      _buildSettingsScreen(),
    ];

    return Scaffold(
      appBar: AppBar(
        title: Text(
          _selectedIndex == 0
              ? 'Dashboard'
              : _selectedIndex == 1
              ? 'Analytics'
              : _selectedIndex == 2
              ? 'Seasonal Trends'
              : _selectedIndex == 3
              ? 'Capacity Utilization'
              : _selectedIndex == 4
              ? 'Custom Reports'
              : _selectedIndex == 5
              ? 'Reports'
              : 'Settings',
          style: const TextStyle(color: Colors.white, fontSize: 16),
        ),
        backgroundColor: const Color(0xff0d2039),
        elevation: 0,
        actions: [
          _buildAlertBellAction(),
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.white),
            onPressed: () => _loadAllData(),
            tooltip: 'Refresh',
          ),
          PopupMenuButton<String>(
            icon: const Icon(Icons.more_vert, color: Colors.white),
            onSelected: (value) {
              if (value == 'logout') {
                _handleLogout();
              }
            },
            itemBuilder: (context) => [
              PopupMenuItem(
                value: 'profile',
                child: Row(
                  children: [
                    const Icon(Icons.person),
                    const SizedBox(width: 8),
                    Text(widget.adminData['name'] ?? 'Admin'),
                  ],
                ),
              ),
              const PopupMenuItem(
                value: 'logout',
                child: Row(
                  children: [
                    Icon(Icons.logout, color: Colors.red),
                    SizedBox(width: 8),
                    Text('Logout', style: TextStyle(color: Colors.red)),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
      body: Stack(
        children: [
          screens[_selectedIndex],
          // Loading overlay when data is being loaded
          if (_isLoadingStats)
            Container(
              color: Colors.black.withOpacity(0.3),
              child: Center(
                child: Card(
                  elevation: 8,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(32),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const CircularProgressIndicator(
                          strokeWidth: 3,
                        ),
                        const SizedBox(height: 16),
                        Text(
                          'Loading Dashboard Data...',
                          style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Please wait while we fetch the latest information',
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: Colors.grey[600],
                          ),
                          textAlign: TextAlign.center,
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
      bottomNavigationBar: Container(
        color: Colors.grey.shade100,
        height: 80,
        child: SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              _buildNavTab('Dashboard', Icons.dashboard_outlined, Icons.dashboard, 0),
              _buildNavTab('Analytics', Icons.analytics_outlined, Icons.analytics, 1),
              _buildNavTab('Seasons', Icons.calendar_month_outlined, Icons.calendar_month, 2),
              _buildNavTab('Capacity', Icons.storage_outlined, Icons.storage, 3),
              _buildNavTab('Custom', Icons.assessment_outlined, Icons.assessment, 4),
              _buildNavTab('Reports', Icons.description_outlined, Icons.description, 5),
              _buildNavTab('Settings', Icons.settings_outlined, Icons.settings, 6),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildNavTab(String label, IconData outlineIcon, IconData filledIcon, int index) {
    return GestureDetector(
      onTap: () => setState(() => _selectedIndex = index),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        decoration: BoxDecoration(
          color: _selectedIndex == index ? Colors.blue.shade100 : Colors.transparent,
          border: Border(
            bottom: BorderSide(
              color: _selectedIndex == index ? Colors.blue : Colors.transparent,
              width: 3,
            ),
          ),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              _selectedIndex == index ? filledIcon : outlineIcon,
              color: _selectedIndex == index ? Colors.blue : Colors.grey,
              size: 20,
            ),
            const SizedBox(height: 2),
            Text(
              label,
              style: TextStyle(
                color: _selectedIndex == index ? Colors.blue : Colors.grey,
                fontSize: 10,
                fontWeight: _selectedIndex == index ? FontWeight.bold : FontWeight.normal,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDashboardHome() {
    final todayData = _weeklyForecast.isNotEmpty ? _weeklyForecast.first : null;
    final todayWeather = _weatherData.isNotEmpty ? _weatherData.first : null;

    return RefreshIndicator(
      onRefresh: _loadAllData,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Dashboard',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 16),

            // CURRENT WEATHER SECTION
            if (todayWeather != null)
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Current Weather',
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        colors: [Colors.orange.shade300, Colors.orange.shade600],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'Sigiriya, Sri Lanka',
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 14,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  _formatWeatherValue(todayWeather['temperature']) + '°C',
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 36,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ],
                            ),
                            Icon(
                              Icons.cloud_queue,
                              size: 48,
                              color: Colors.white.withOpacity(0.8),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        Text(
                          todayWeather['condition'] ?? 'Unknown',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 16,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'Rainfall',
                                    style: TextStyle(
                                      color: Colors.white.withOpacity(0.8),
                                      fontSize: 12,
                                    ),
                                  ),
                                  Text(
                                    _formatWeatherValue(todayWeather['rainfall']) + ' mm',
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontSize: 14,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'Wind Speed',
                                    style: TextStyle(
                                      color: Colors.white.withOpacity(0.8),
                                      fontSize: 12,
                                    ),
                                  ),
                                  Text(
                                    _formatWeatherValue(todayWeather['wind_speed']) + ' m/s',
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontSize: 14,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),
                ],
              ),

            // TODAY'S STATUS
            if (todayData != null && todayWeather != null)
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Today\'s Status',
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: Colors.blue.shade50,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(color: Colors.blue.shade200),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Icon(Icons.people, color: Colors.blue.shade600),
                                  const SizedBox(width: 8),
                                  Text(
                                    'Visitors',
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: Colors.blue.shade600,
                                      fontWeight: FontWeight.w500,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 8),
                              Text(
                                '${_getCrowdValue(todayData)}',
                                style: const TextStyle(
                                  fontSize: 28,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                'Expected today',
                                style: TextStyle(
                                  fontSize: 11,
                                  color: Colors.grey.shade600,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: Colors.orange.shade50,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(color: Colors.orange.shade200),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Icon(Icons.cloud, color: Colors.orange.shade600),
                                  const SizedBox(width: 8),
                                  Text(
                                    'Temperature',
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: Colors.orange.shade600,
                                      fontWeight: FontWeight.w500,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 8),
                              Text(
                                '${(todayWeather['temperature'] as num).toStringAsFixed(1)}°C',
                                style: const TextStyle(
                                  fontSize: 28,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                'Rain: ${(todayWeather['rainfall'] as num).toStringAsFixed(1)}mm',
                                style: TextStyle(
                                  fontSize: 11,
                                  color: Colors.grey.shade600,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 24),
                ],
              ),

            // OVERVIEW
            Text(
              'Overview',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 12),
            if (_isLoadingStats)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(32),
                  child: CircularProgressIndicator(),
                ),
              )
            else
              GridView.count(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                crossAxisCount: 2,
                mainAxisSpacing: 12,
                crossAxisSpacing: 12,
                childAspectRatio: 1.4,
                children: [
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.blue.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: Colors.blue.withOpacity(0.3)),
                    ),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.people, color: Colors.blue, size: 28),
                        const SizedBox(height: 8),
                        Text(
                          '${_dashboardStats['total_visitors'] ?? 0}',
                          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.blue),
                        ),
                        const Text('Total Visitors', style: TextStyle(fontSize: 11, color: Colors.grey)),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.green.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: Colors.green.withOpacity(0.3)),
                    ),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.chat, color: Colors.green, size: 28),
                        const SizedBox(height: 8),
                        Text(
                          '${_dashboardStats['active_chats'] ?? 0}',
                          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.green),
                        ),
                        const Text('Active Chats', style: TextStyle(fontSize: 11, color: Colors.grey)),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.orange.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: Colors.orange.withOpacity(0.3)),
                    ),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.trending_up, color: Colors.orange, size: 28),
                        const SizedBox(height: 8),
                        Text(
                          '${_dashboardStats['daily_average'] ?? _dashboardStats['today_visits'] ?? 0}',
                          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.orange),
                        ),
                        const Text('Daily Average', style: TextStyle(fontSize: 11, color: Colors.grey)),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.purple.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: Colors.purple.withOpacity(0.3)),
                    ),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.message, color: Colors.purple, size: 28),
                        const SizedBox(height: 8),
                        Text(
                          '${(_dashboardStats['total_messages'] ?? 0) ~/ 60}',
                          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.purple),
                        ),
                        const Text('Messages', style: TextStyle(fontSize: 11, color: Colors.grey)),
                      ],
                    ),
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildAnalyticsScreen() {
    if (_weeklyForecast.isEmpty) {
      return RefreshIndicator(
        onRefresh: _loadAllData,
        child: Center(
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.analytics, size: 64, color: Colors.grey),
                const SizedBox(height: 16),
                const Text('Loading Analytics Data...'),
                const SizedBox(height: 8),
                Text(
                  'Pull down to refresh',
                  style: TextStyle(color: Colors.grey.shade600, fontSize: 12),
                ),
              ],
            ),
          ),
        ),
      );
    }

    final weekData = _weeklyForecast.take(7).toList();
    final monthData = _weeklyForecast.take(30).toList();
    int weeklyTotal = 0;
    int monthlyTotal = 0;
    double weekAvgTemp = 0;
    double monthAvgTemp = 0;
    int maxMonthlyVisitors = 0;

    for (var d in weekData) {
      try {
        final visitors = d['visitors'];
        if (visitors is num) {
          weeklyTotal += visitors.toInt();
        } else if (visitors is String) {
          weeklyTotal += int.parse(visitors);
        }
      } catch (e) {
        print('Error parsing weekly visitor: $e, value: ${d['visitors']}');
      }
    }

    for (var d in monthData) {
      try {
        final visitors = _getCrowdValue(d);
        monthlyTotal += visitors;
        if (visitors > maxMonthlyVisitors) {
          maxMonthlyVisitors = visitors;
        }
      } catch (e) {
        print('Error parsing monthly visitor: $e, value: ${d['visitors']}');
      }
    }

    if (_weatherData.isNotEmpty) {
      int weatherCount = _weatherData.take(7).length;
      for (var d in _weatherData.take(7)) {
        try {
          final temp = d['temperature'];
          if (temp is num) {
            weekAvgTemp += temp.toDouble();
          } else if (temp is String) {
            weekAvgTemp += double.parse(temp);
          }
        } catch (e) {
          print('Error parsing temperature: $e, value: ${d['temperature']}');
        }
      }
      if (weatherCount > 0) weekAvgTemp = weekAvgTemp / weatherCount;
    }

    if (_weatherData.isNotEmpty) {
      int weatherCount = _weatherData.take(30).length;
      for (var d in _weatherData.take(30)) {
        try {
          final temp = d['temperature'];
          if (temp is num) {
            monthAvgTemp += temp.toDouble();
          } else if (temp is String) {
            monthAvgTemp += double.parse(temp);
          }
        } catch (e) {
          print('Error parsing temperature: $e, value: ${d['temperature']}');
        }
      }
      if (weatherCount > 0) monthAvgTemp = monthAvgTemp / weatherCount;
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Monthly Expected Crowds
          Text(
            'Monthly Expected Crowds Forecast',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.grey.shade100,
              borderRadius: BorderRadius.circular(12),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.05),
                  blurRadius: 4,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: SizedBox(
              height: 300,
              child: _buildMonthlyBarChart(monthData, maxMonthlyVisitors),
            ),
          ),
          const SizedBox(height: 32),

          // Weekly Crowd Expectations Line Graph
          Text(
            'Weekly Crowd Expectations (Next 7 Days)',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.grey.shade100,
              borderRadius: BorderRadius.circular(12),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.05),
                  blurRadius: 4,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: SizedBox(
              height: 280,
              child: _buildWeeklyLineChart(weekData),
            ),
          ),
          const SizedBox(height: 32),

          // Daily 7-Day Detailed Prediction
          Text(
            'Daily Crowd Prediction (Next 7 Days)',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.grey.shade100,
              borderRadius: BorderRadius.circular(12),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.05),
                  blurRadius: 4,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: SizedBox(
              height: 300,
              child: _buildDailyBarChart(weekData),
            ),
          ),
          const SizedBox(height: 32),

          // Summary Cards
          Text(
            'Weekly Summary',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 16),
          GridView.count(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            crossAxisCount: 2,
            mainAxisSpacing: 12,
            crossAxisSpacing: 12,
            children: [
              _buildSummaryCard('Total Visitors', '$weeklyTotal', Icons.people, Colors.blue),
              _buildSummaryCard('Daily Avg', '${(weeklyTotal ~/ 7)}', Icons.trending_up, Colors.green),
              _buildSummaryCard('Avg Temp', '${weekAvgTemp.toStringAsFixed(1)}°C', Icons.thermostat, Colors.orange),
              _buildSummaryCard('Days', '7', Icons.calendar_today, Colors.purple),
            ],
          ),
          const SizedBox(height: 32),

          Text(
            'Monthly Summary (30 Days)',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 16),
          GridView.count(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            crossAxisCount: 2,
            mainAxisSpacing: 12,
            crossAxisSpacing: 12,
            children: [
              _buildSummaryCard('Total Visitors', '$monthlyTotal', Icons.people, Colors.blue),
              _buildSummaryCard('Daily Avg', '${(monthlyTotal ~/ 30)}', Icons.trending_up, Colors.green),
              _buildSummaryCard('Avg Temp', '${monthAvgTemp.toStringAsFixed(1)}°C', Icons.thermostat, Colors.orange),
              _buildSummaryCard('Days', '30', Icons.calendar_today, Colors.purple),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildMonthlyBarChart(List<dynamic> data, int maxValue) {
    // Use XGBoost model monthly data if available, otherwise compute from daily
    Map<String, int> monthlyData = {};
    
    if (_monthlyForecast.isNotEmpty) {
      print('✓ Using XGBoost model monthly predictions');
      
      // Map full month names to abbreviated names
      final monthMapping = {
        'January': 'Jan', 'February': 'Feb', 'March': 'Mar', 'April': 'Apr',
        'May': 'May', 'June': 'Jun', 'July': 'Jul', 'August': 'Aug',
        'September': 'Sep', 'October': 'Oct', 'November': 'Nov', 'December': 'Dec'
      };
      
      for (var entry in _monthlyForecast.entries) {
        final abbrevMonth = monthMapping[entry.key] ?? entry.key;
        monthlyData[abbrevMonth] = entry.value is int ? entry.value : 0;
        print('✓ Mapped ${entry.key} (${entry.value}) → $abbrevMonth');
      }
    } else {
      print('⚠ Computing monthly aggregates from daily forecast');
      monthlyData = _getMonthlyAggregates(data);
    }
    
    if (monthlyData.isEmpty) {
      return Center(
        child: Text(
          'No data available',
          style: TextStyle(color: Colors.grey.shade600),
        ),
      );
    }

    // Ensure all 12 months are present
    final monthNames = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
    ];
    
    // Fill in missing months with data from monthlyData or use default
    for (String month in monthNames) {
      if (!monthlyData.containsKey(month)) {
        // Try to find it with fallback
        monthlyData[month] = 3500; // Default value for missing months
      }
    }
    
    // Get values in order and calculate max
    final values = monthNames.map((m) => (monthlyData[m] ?? 0).toDouble()).toList();
    final actualMax = values.isEmpty ? 5000 : values.reduce((a, b) => a > b ? a : b).toInt();
    final maxDisplayValue = (actualMax > 0 ? (actualMax * 1.2) : 5000).toInt();
    
    print('✓ Monthly chart data: $monthlyData');
    print('✓ Values: $values, Max: $actualMax, Display Max: $maxDisplayValue');

    // Create bar groups for the chart
    List<BarChartGroupData> barGroups = [];
    for (int i = 0; i < monthNames.length; i++) {
      final value = values[i];
      barGroups.add(
        BarChartGroupData(
          x: i,
          barRods: [
            BarChartRodData(
              toY: value,
              color: value > 5000
                  ? (value > 7000 ? Colors.red : Colors.orange)
                  : (value > 1500 ? Colors.amber : Colors.blue),
              width: 20,
              borderRadius: const BorderRadius.vertical(top: Radius.circular(6)),
              backDrawRodData: BackgroundBarChartRodData(
                show: true,
                toY: maxDisplayValue.toDouble(),
                color: Colors.grey.withOpacity(0.1),
              ),
            ),
          ],
        ),
      );
    }

    return BarChart(
      BarChartData(
        barGroups: barGroups,
        gridData: FlGridData(
          show: true,
          drawVerticalLine: false,
          horizontalInterval: maxDisplayValue > 0 ? (maxDisplayValue / 4).toInt().toDouble() : 1000,
          getDrawingHorizontalLine: (value) {
            return FlLine(
              color: Colors.grey.withOpacity(0.2),
              strokeWidth: 1,
            );
          },
        ),
        titlesData: FlTitlesData(
          show: true,
          topTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
          rightTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              getTitlesWidget: (value, meta) {
                int index = value.toInt();
                if (index < 0 || index >= monthNames.length) {
                  return const Text('');
                }
                return Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(
                    monthNames[index],
                    style: const TextStyle(fontSize: 11, color: Colors.grey),
                  ),
                );
              },
            ),
          ),
          leftTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              getTitlesWidget: (value, meta) {
                return Text(
                  '${(value ~/ 1000)}k',
                  style: const TextStyle(fontSize: 10, color: Colors.grey),
                );
              },
              reservedSize: 40,
            ),
          ),
        ),
        borderData: FlBorderData(show: true, border: Border.all(color: Colors.grey.shade300)),
        maxY: maxDisplayValue.toDouble(),
        minY: 0,
        barTouchData: BarTouchData(
          enabled: true,
          touchTooltipData: BarTouchTooltipData(
            getTooltipColor: (_) => Colors.grey.shade800,
            getTooltipItem: (group, groupIndex, rod, rodIndex) {
              return BarTooltipItem(
                '${monthNames[groupIndex]}\n${rod.toY.toInt()} visitors',
                const TextStyle(color: Colors.white, fontSize: 11),
              );
            },
          ),
        ),
      ),
    );
  }

  Widget _buildWeeklyLineChart(List<dynamic> data) {
    final spots = <FlSpot>[];
    int maxValue = 0;
    
    for (int i = 0; i < data.length && i < 7; i++) {
      try {
        final visitors = _getCrowdValue(data[i]).toDouble();
        spots.add(FlSpot(i.toDouble(), visitors));
        if (visitors.toInt() > maxValue) {
          maxValue = visitors.toInt();
        }
      } catch (e) {
        spots.add(FlSpot(i.toDouble(), 0));
      }
    }

    final maxDisplayValue = maxValue > 0 ? (maxValue * 1.15).toInt() : 5000;
    final dayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

    return LineChart(
      LineChartData(
        gridData: FlGridData(
          show: true,
          drawVerticalLine: false,
          horizontalInterval: maxDisplayValue > 0 ? (maxDisplayValue / 4).toInt().toDouble() : 1000,
          getDrawingHorizontalLine: (value) {
            return FlLine(
              color: Colors.grey.withOpacity(0.2),
              strokeWidth: 1,
            );
          },
        ),
        titlesData: FlTitlesData(
          show: true,
          topTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
          rightTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              getTitlesWidget: (value, meta) {
                int index = value.toInt();
                if (index < 0 || index >= dayLabels.length) return const Text('');
                return Text(
                  dayLabels[index],
                  style: const TextStyle(fontSize: 11, color: Colors.grey),
                );
              },
            ),
          ),
          leftTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              getTitlesWidget: (value, meta) {
                return Text(
                  value.toInt().toString(),
                  style: const TextStyle(fontSize: 10, color: Colors.grey),
                );
              },
              reservedSize: 40,
            ),
          ),
        ),
        borderData: FlBorderData(show: true, border: Border.all(color: Colors.grey.shade300)),
        lineBarsData: [
          LineChartBarData(
            spots: spots,
            isCurved: true,
            gradient: LinearGradient(
              colors: [Colors.teal.shade400, Colors.teal.shade800],
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
            ),
            barWidth: 3,
            isStrokeCapRound: true,
            dotData: FlDotData(
              show: true,
              getDotPainter: (spot, percent, barData, index) {
                return FlDotCirclePainter(
                  radius: 6,
                  color: Colors.teal.shade600,
                  strokeWidth: 2,
                  strokeColor: Colors.white,
                );
              },
            ),
            belowBarData: BarAreaData(
              show: true,
              gradient: LinearGradient(
                colors: [Colors.teal.withOpacity(0.3), Colors.teal.withOpacity(0.01)],
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
              ),
            ),
          ),
        ],
        minY: 0,
        maxY: maxDisplayValue.toDouble(),
      ),
    );
  }

  Widget _buildDailyBarChart(List<dynamic> data) {
    List<BarChartGroupData> barGroups = [];
    int maxValue = 0;
    final dayLabels = ['Day 1', 'Day 2', 'Day 3', 'Day 4', 'Day 5', 'Day 6', 'Day 7'];

    for (int i = 0; i < data.length && i < 7; i++) {
      try {
        final visitors = _getCrowdValue(data[i]);
        if (visitors > maxValue) maxValue = visitors;
        
        barGroups.add(
          BarChartGroupData(
            x: i,
            barRods: [
              BarChartRodData(
                toY: visitors.toDouble(),
                color: visitors > 5000
                    ? (visitors > 7000 ? Colors.red : Colors.orange)
                    : (visitors > 1500 ? Colors.amber : Colors.blue),
                width: 22,
                borderRadius: const BorderRadius.vertical(top: Radius.circular(6)),
                backDrawRodData: BackgroundBarChartRodData(
                  show: true,
                  toY: (maxValue * 1.2).toDouble(),
                  color: Colors.grey.withOpacity(0.1),
                ),
              ),
            ],
          ),
        );
      } catch (e) {
        barGroups.add(
          BarChartGroupData(
            x: i,
            barRods: [
              BarChartRodData(
                toY: 0,
                color: Colors.grey.shade300,
                width: 22,
              ),
            ],
          ),
        );
      }
    }

    final maxDisplayValue = (maxValue * 1.2).toInt();

    return BarChart(
      BarChartData(
        barGroups: barGroups,
        gridData: FlGridData(
          show: true,
          drawVerticalLine: false,
          horizontalInterval: maxDisplayValue > 0 ? (maxDisplayValue / 4).toInt().toDouble() : 1000,
          getDrawingHorizontalLine: (value) {
            return FlLine(
              color: Colors.grey.withOpacity(0.2),
              strokeWidth: 1,
            );
          },
        ),
        titlesData: FlTitlesData(
          show: true,
          topTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
          rightTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              getTitlesWidget: (value, meta) {
                int index = value.toInt();
                if (index < 0 || index >= dayLabels.length) return const Text('');
                return Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(
                    dayLabels[index],
                    style: const TextStyle(fontSize: 11, color: Colors.grey),
                  ),
                );
              },
            ),
          ),
          leftTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              getTitlesWidget: (value, meta) {
                return Text(
                  value.toInt().toString(),
                  style: const TextStyle(fontSize: 10, color: Colors.grey),
                );
              },
              reservedSize: 40,
            ),
          ),
        ),
        borderData: FlBorderData(show: true, border: Border.all(color: Colors.grey.shade300)),
        maxY: maxDisplayValue.toDouble(),
        minY: 0,
        barTouchData: BarTouchData(
          enabled: true,
          touchTooltipData: BarTouchTooltipData(
            getTooltipColor: (_) => Colors.grey.shade800,
            getTooltipItem: (group, groupIndex, rod, rodIndex) {
              return BarTooltipItem(
                '${dayLabels[groupIndex]}\n${rod.toY.toInt()} visitors',
                const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold),
              );
            },
          ),
        ),
      ),
    );
  }

  Widget _buildSummaryCard(String label, String value, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.2)),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, color: color, size: 32),
          const SizedBox(height: 8),
          Text(
            value,
            style: TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            label,
            style: TextStyle(
              fontSize: 12,
              color: Colors.grey.shade600,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  // FEATURE 1: SEASONAL TRENDS HIGHLIGHT
  Widget _buildSeasonalTrendsScreen() {
    final monthNames = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December'
    ];
    final peakSeasons = [0, 6, 7, 11]; // Jan, Jul, Aug, Dec (0-indexed)
    
    // Calculate average across all months
    final monthlyValues = _monthlyForecast.values.whereType<int>().toList();
    final avgVisitors = monthlyValues.isEmpty ? 0 : (monthlyValues.reduce((a, b) => a + b) / monthlyValues.length).toInt();
    
    // Classification thresholds
    final lowThreshold = (avgVisitors * 0.8).toInt();
    final highThreshold = (avgVisitors * 1.2).toInt();
    
    return RefreshIndicator(
      onRefresh: _loadAllData,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Seasonal Trends Analysis',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(
              'Predicted visitor patterns for 2026',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey.shade600),
            ),
            const SizedBox(height: 24),
            
            // Summary metrics
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                gradient: LinearGradient(colors: [Colors.blue.shade400, Colors.blue.shade700]),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        'Annual Overview',
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(color: Colors.white, fontWeight: FontWeight.bold),
                      ),
                      Icon(Icons.calendar_today, color: Colors.white70),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceAround,
                    children: [
                      _buildSeasonMetric('Avg Visitors/Day', '$avgVisitors', Colors.white),
                      _buildSeasonMetric('Peak: $highThreshold+', '${peakSeasons.length}mo', Colors.yellow.shade200),
                      _buildSeasonMetric('Low: <$lowThreshold', '${12 - peakSeasons.length}mo', Colors.blue.shade100),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),
            
            // Monthly breakdown
            Text(
              'Month-by-Month Breakdown',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            
            ..._buildMonthlySeasonCards(monthNames, peakSeasons, lowThreshold, highThreshold, avgVisitors),
          ],
        ),
      ),
    );
  }
  
  List<Widget> _buildMonthlySeasonCards(List<String> monthNames, List<int> peakSeasons, int lowThreshold, int highThreshold, int avgVisitors) {
    final daysPerMonth = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    
    List<Widget> cards = [];
    for (int i = 0; i < 12 && i < monthNames.length; i++) {
      final monthName = monthNames[i];
      final visitors = _safeToInt(_monthlyForecast[monthName], avgVisitors);
      
      final isPeakSeason = peakSeasons.contains(i);
      final seasonType = isPeakSeason ? 'Peak Season' : 
                         (visitors < lowThreshold ? 'Low Season' : 'Average Season');
      final seasonColor = isPeakSeason ? Colors.amber : 
                          (visitors < lowThreshold ? Colors.blue : Colors.teal);
      
      final totalMonthVisitors = visitors * daysPerMonth[i];
      
      cards.add(
        Container(
          margin: const EdgeInsets.only(bottom: 12),
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: seasonColor.withOpacity(0.1),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: seasonColor.withOpacity(0.3)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        monthNames[i],
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 4),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: seasonColor,
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: Text(
                          seasonType,
                          style: TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w600),
                        ),
                      ),
                    ],
                  ),
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: seasonColor.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      isPeakSeason ? '⭐' : (visitors < lowThreshold ? '❄️' : '☀️'),
                      style: const TextStyle(fontSize: 24),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Text(
                'Predicted Daily Avg: $visitors visitors',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey.shade700),
              ),
              const SizedBox(height: 4),
              Text(
                'Total for Month: ${totalMonthVisitors ~/ 1000}K visitors',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey.shade700),
              ),
              const SizedBox(height: 12),
              Text(
                _getSeasonalRecommendation(seasonType, visitors, avgVisitors),
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Colors.grey.shade700,
                  fontStyle: FontStyle.italic,
                ),
              ),
            ],
          ),
        ),
      );
    }
    return cards;
  }
  
  Widget _buildSeasonMetric(String label, String value, Color color) {
    return Column(
      children: [
        Text(value, style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: color)),
        const SizedBox(height: 4),
        Text(label, style: TextStyle(fontSize: 11, color: color.withOpacity(0.9))),
      ],
    );
  }
  
  String _getSeasonalRecommendation(String season, int visitors, int avg) {
    if (season == 'Peak Season') {
      return '→ Maximize staffing levels, consider premium pricing and special events. Book accommodations early.';
    } else if (season == 'Low Season') {
      return '→ Focus on marketing campaigns and discounts. Ideal for maintenance and training activities.';
    } else {
      return '→ Steady visitor flow. Standard operational procedures. Plan for seasonal transitions.';
    }
  }

  // FEATURE 2: CAPACITY UTILIZATION ANALYSIS
  Widget _buildCapacityUtilizationScreen() {
    return RefreshIndicator(
      onRefresh: _loadAllData,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Capacity Utilization',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 24),
            
            // Facility Capacity Summary
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                gradient: LinearGradient(colors: [Colors.purple.shade400, Colors.purple.shade700]),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Sigiriya Facility Capacity',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(color: Colors.white, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceAround,
                    children: [
                      _buildCapacityBadge('Maximum', '$_facilityCapacity', Colors.white),
                      _buildCapacityBadge('90% Level', '${(_facilityCapacity * 0.9).toInt()}', Colors.orange.shade100),
                      _buildCapacityBadge('80% Level', '${(_facilityCapacity * 0.8).toInt()}', Colors.yellow.shade100),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),
            
            // Capacity Thresholds & Critical Dates
            Text(
              'Critical Dates & Capacity Thresholds',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            
            ..._buildCapacityAnalysis(),
          ],
        ),
      ),
    );
  }
  
  List<Widget> _buildCapacityAnalysis() {
    final monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
    final avgVisitors = _monthlyForecast.values.whereType<int>().toList();
    final avgMonthly = avgVisitors.isEmpty ? 0 : (avgVisitors.reduce((a, b) => a + b) / avgVisitors.length).toInt();
    
    List<Widget> widgets = [];
    
    for (int i = 0; i < 12 && i < monthNames.length; i++) {
      final monthName = monthNames[i];
      final dailyVisitors = _safeToInt(_monthlyForecast[monthName], avgMonthly);
      
      final capacity80 = (_facilityCapacity * 0.8).toInt();
      final capacity90 = (_facilityCapacity * 0.9).toInt();
      final utilization = _facilityCapacity > 0 ? ((dailyVisitors / _facilityCapacity) * 100).toInt() : 0;
      
      Color statusColor = Colors.green;
      String statusLabel = 'Safe';
      String warningLevel = '✓ Safe';
      IconData statusIcon = Icons.check_circle;
      
      if (dailyVisitors > _facilityCapacity) {
        statusColor = Colors.red;
        statusLabel = 'Overcrowded';
        warningLevel = '⚠ Critical - Crowd Management Required';
        statusIcon = Icons.error;
      } else if (dailyVisitors > capacity90) {
        statusColor = Colors.orange;
        statusLabel = 'Crowded';
        warningLevel = '⚠ High - Close Monitoring Needed';
        statusIcon = Icons.warning;
      } else if (dailyVisitors > capacity80) {
        statusColor = Colors.amber;
        statusLabel = 'Getting Busy';
        warningLevel = '⚠ Moderate - Prepare Resources';
        statusIcon = Icons.info;
      }
      
      widgets.add(
        Container(
          margin: const EdgeInsets.only(bottom: 12),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: statusColor.withOpacity(0.1),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: statusColor.withOpacity(0.3)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        monthName,
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 4),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: statusColor,
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(statusIcon, color: Colors.white, size: 14),
                            const SizedBox(width: 6),
                            Text(
                              statusLabel,
                              style: TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w600),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  Text(
                    '$utilization%',
                    style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: statusColor),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: LinearProgressIndicator(
                  value: _facilityCapacity > 0 ? (dailyVisitors / _facilityCapacity).clamp(0.0, 1.2) : 0.0,
                  minHeight: 8,
                  backgroundColor: Colors.grey.shade300,
                  valueColor: AlwaysStoppedAnimation<Color>(statusColor),
                ),
              ),
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Daily Avg: $dailyVisitors visitors',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey.shade700),
                  ),
                  Text(
                    'Capacity: $_facilityCapacity',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey.shade700),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: statusColor.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  warningLevel,
                  style: TextStyle(color: statusColor, fontSize: 12, fontWeight: FontWeight.w600),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                _getCapacityRecommendation(statusLabel, dailyVisitors),
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Colors.grey.shade700,
                  fontStyle: FontStyle.italic,
                ),
              ),
            ],
          ),
        ),
      );
    }
    
    return widgets;
  }
  
  Widget _buildCapacityBadge(String label, String value, Color color) {
    return Column(
      children: [
        Text(value, style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: color)),
        const SizedBox(height: 4),
        Text(label, style: TextStyle(fontSize: 11, color: color.withOpacity(0.9))),
      ],
    );
  }
  
  String _getCapacityRecommendation(String status, int visitors) {
    if (status == 'Overcrowded') {
      return '→ URGENT: Implement crowd control measures, consider time-slot restrictions, increase security staff.';
    } else if (status == 'Crowded') {
      return '→ Alert staff to heightened alertness, prepare rapid response team, monitor real-time counts.';
    } else if (status == 'Getting Busy') {
      return '→ Resource check: Ensure sufficient staff, guides, and facilities are available.';
    } else {
      return '→ Normal operations. Routine monitoring sufficient.';
    }
  }

  // FEATURE 3: CUSTOM DATE RANGE SELECTOR & REPORTS
  Widget _buildCustomReportScreen() {
    return RefreshIndicator(
      onRefresh: _loadAllData,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Custom Report Generator',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 24),
            
            // Date Range Selection
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.blue.shade50,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.blue.shade200),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Select Analysis Period',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Expanded(
                        child: GestureDetector(
                          onTap: () => _selectStartDate(),
                          child: Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: Colors.blue.shade300),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text('From', style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey)),
                                const SizedBox(height: 4),
                                Text(
                                  '${_selectedStartDate.year}-${_selectedStartDate.month.toString().padLeft(2, '0')}-${_selectedStartDate.day.toString().padLeft(2, '0')}',
                                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.bold),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: GestureDetector(
                          onTap: () => _selectEndDate(),
                          child: Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: Colors.blue.shade300),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text('To', style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey)),
                                const SizedBox(height: 4),
                                Text(
                                  '${_selectedEndDate.year}-${_selectedEndDate.month.toString().padLeft(2, '0')}-${_selectedEndDate.day.toString().padLeft(2, '0')}',
                                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.bold),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'Duration: ${_selectedEndDate.difference(_selectedStartDate).inDays + 1} days',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey.shade700),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),
            
            // Comparison Period Analysis
            Text(
              'Period Comparison',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            
            ..._buildPeriodComparison(),
          ],
        ),
      ),
    );
  }
  
  Future<void> _selectStartDate() async {
    final DateTime? picked = await showDatePicker(
      context: context,
      initialDate: _selectedStartDate,
      firstDate: DateTime(2025),
      lastDate: DateTime(2027),
    );
    if (picked != null && picked != _selectedStartDate) {
      setState(() => _selectedStartDate = picked);
    }
  }
  
  Future<void> _selectEndDate() async {
    final DateTime? picked = await showDatePicker(
      context: context,
      initialDate: _selectedEndDate,
      firstDate: DateTime(2025),
      lastDate: DateTime(2027),
    );
    if (picked != null && picked != _selectedEndDate) {
      setState(() => _selectedEndDate = picked);
    }
  }
  
  List<Widget> _buildPeriodComparison() {
    final monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
    final monthlyValues = _monthlyForecast.values.whereType<int>().toList();
    final avgMonthly = monthlyValues.isEmpty ? 0 : (monthlyValues.reduce((a, b) => a + b) / monthlyValues.length).toInt();
    
    int selectedPeriodVisitors = 0;
    int daysInPeriod = _selectedEndDate.difference(_selectedStartDate).inDays + 1;
    
    // Calculate visitors for selected date range
    DateTime current = _selectedStartDate;
    while (current.isBefore(_selectedEndDate) || current.isAtSameMomentAs(_selectedEndDate)) {
      final monthIndex = current.month - 1;
      final monthName = monthNames[monthIndex];
      final dailyVisitors = _safeToInt(_monthlyForecast[monthName], avgMonthly);
      selectedPeriodVisitors += dailyVisitors;
      current = current.add(const Duration(days: 1));
    }
    
    final avgDailyVisitors = (selectedPeriodVisitors / daysInPeriod).toInt();
    
    return [
      Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.green.shade50,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: Colors.green.shade200),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Selected Period Summary',
              style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            _buildComparisonRow('Total Visitors', selectedPeriodVisitors.toString(), Colors.blue),
            _buildComparisonRow('Average Daily', '$avgDailyVisitors visitors', Colors.teal),
            _buildComparisonRow('Days in Period', '$daysInPeriod days', Colors.orange),
          ],
        ),
      ),
      const SizedBox(height: 24),
      Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.purple.shade50,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: Colors.purple.shade200),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Full Year 2026 Comparison',
              style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            _buildComparisonRow('Total Annual Visitors', monthlyValues.isEmpty ? '0' : '${monthlyValues.reduce((a, b) => a + b) * 30}', Colors.blue),
            _buildComparisonRow('Monthly Average', '$avgMonthly visitors/day', Colors.teal),
          ],
        ),
      ),
      const SizedBox(height: 24),
      Center(
        child: ElevatedButton.icon(
          onPressed: () => _generateCustomReport(),
          icon: const Icon(Icons.download),
          label: const Text('Generate & Export Report'),
          style: ElevatedButton.styleFrom(
            backgroundColor: Colors.blue,
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
          ),
        ),
      ),
    ];
  }
  
  Widget _buildComparisonRow(String label, String value, Color color) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.grey.shade700)),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: color.withOpacity(0.2),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              value,
              style: TextStyle(color: color, fontWeight: FontWeight.w600, fontSize: 13),
            ),
          ),
        ],
      ),
    );
  }
  
  void _generateCustomReport() {
    final monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
    StringBuffer report = StringBuffer();
    report.writeln('CUSTOM VISITOR FORECAST REPORT');
    report.writeln('Generated: ${DateTime.now()}');
    report.writeln('Period: ${_selectedStartDate.toString().split(' ')[0]} to ${_selectedEndDate.toString().split(' ')[0]}');
    report.writeln('');
    report.writeln('Monthly Forecast Data:');
    report.writeln('Month,Avg Daily Visitors,Days,Total Visitors,Est Revenue');
    
    final daysPerMonth = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    int totalAnnualVisitors = 0;
    int totalRevenue = 0;
    
    for (int i = 0; i < 12 && i < monthNames.length; i++) {
      final monthName = monthNames[i];
      final dailyVisitors = _safeToInt(_monthlyForecast[monthName], 3500);
      final monthTotal = dailyVisitors * daysPerMonth[i];
      final monthRevenue = monthTotal * 37;
      report.writeln('$monthName,$dailyVisitors,${daysPerMonth[i]},$monthTotal,$monthRevenue');
      totalAnnualVisitors += monthTotal;
      totalRevenue += monthRevenue;
    }
    
    report.writeln('');
    report.writeln('ANNUAL SUMMARY');
    report.writeln('Total Visitors: $totalAnnualVisitors');
    report.writeln('Total Revenue: \$$totalRevenue');
    
    _showCSVDialog('Custom Report Export', report.toString());
  }

  Widget _buildReportsScreen() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Data Reports',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 24),
          
          _buildReportTile(
            'Crowd Predictions',
            'Full year 2026 visitor forecasts',
            Icons.people,
            Colors.blue,
            '${_weeklyForecast.length} days',
            () => _exportCrowdDataAsCSV(),
          ),
          const SizedBox(height: 12),
          
          _buildReportTile(
            'Weather Predictions',
            'Temperature, rainfall & wind data',
            Icons.cloud,
            Colors.orange,
            '${_weatherData.length} days',
            () => _exportWeatherDataAsCSV(),
          ),
          const SizedBox(height: 24),
          
          Text(
            'Report Contents',
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 12),
          
          _buildReportInfo('Crowd Data', [
            '✓ Daily visitor predictions',
            '✓ Upper and lower bounds',
            '✓ Date information',
          ]),
          const SizedBox(height: 16),
          
          _buildReportInfo('Weather Data', [
            '✓ Temperature forecasts',
            '✓ Rainfall predictions',
            '✓ Wind speed data',
          ]),
        ],
      ),
    );
  }

  Widget _buildReportTile(
    String title,
    String description,
    IconData icon,
    Color color,
    String duration,
    VoidCallback onDownload,
  ) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: color, size: 28),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      description,
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.grey.shade600,
                      ),
                    ),
                  ],
                ),
              ),
              ElevatedButton.icon(
                onPressed: onDownload,
                icon: const Icon(Icons.download, size: 18),
                label: const Text('Download'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: color,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: Colors.grey.shade100,
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(
              duration,
              style: TextStyle(
                fontSize: 11,
                color: Colors.grey.shade700,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildReportInfo(String title, List<String> items) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.grey.shade50,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          ...items.map((item) => Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Text(
              item,
              style: TextStyle(
                fontSize: 12,
                color: Colors.grey.shade700,
              ),
            ),
          )),
        ],
      ),
    );
  }

  Widget _buildSettingsScreen() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Configuration & Settings',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 24),

          // Crowd Alert Thresholds Section
          _buildSettingSection(
            'Crowd Alert Thresholds',
            Icons.warning_amber,
            Colors.orange,
            [
              _buildSettingCard(
                'Standard Alert Threshold',
                'Trigger RED alert when visitors > 1500/day',
                '1500 visitors/day',
                Icons.warning_outlined,
              ),
              _buildSettingCard(
                'High Alert Threshold',
                'Trigger orange alert when visitors > 5000/day',
                '5000 visitors/day',
                Icons.trending_up,
              ),
              _buildSettingCard(
                'Critical Alert Threshold',
                'Trigger red alert when visitors > 7000/day',
                '7000 visitors/day',
                Icons.error,
              ),
            ],
          ),
          const SizedBox(height: 24),

          // Prediction Models Section
          _buildSettingSection(
            'Prediction Models',
            Icons.smart_toy,
            Colors.blue,
            [
              _buildSettingCard(
                'Crowd Prediction Model',
                'Uses XGBoost with feature engineering (month, weekday, season, holidays, day-of-year, week-of-year, quarter, lag values, rolling averages)',
                'XGBoost Model v1.0',
                Icons.model_training,
              ),
              _buildSettingCard(
                'Weather Forecast Model',
                'Uses Facebook Prophet time-series forecasting for temperature, rainfall, and wind predictions',
                'Facebook Prophet v1.1',
                Icons.cloud,
              ),
              _buildSettingCard(
                'Features Used',
                'Month, is_weekend, peak_season_flag, holiday_flag, day_of_year, week_of_year, quarter, lag_1, lag_7, rolling_mean_7',
                'Configured',
                Icons.settings,
              ),
            ],
          ),
          const SizedBox(height: 24),

          // API Configuration Section
          _buildSettingSection(
            'API Configuration',
            Icons.api,
            Colors.green,
            [
              _buildSettingCard(
                'API Base URL',
                'Backend server for forecasts and weather data',
                'http://10.0.2.2:8000',
                Icons.language,
              ),
              _buildSettingCard(
                'Forecast Endpoint',
                'Returns 90-day crowd predictions with confidence intervals',
                '/forecast',
                Icons.trending_up,
              ),
              _buildSettingCard(
                'Weather Endpoint',
                'Returns 30-day weather forecast data',
                '/weather_forecast',
                Icons.cloud_download,
              ),
              _buildSettingCard(
                'Fallback Data',
                'Uses synthetic data when API is unavailable or slow',
                'Enabled',
                Icons.backup,
              ),
            ],
          ),
          const SizedBox(height: 24),

          // Notification Settings Section
          _buildSettingSection(
            'Notification Preferences',
            Icons.notifications,
            Colors.red,
            [
              _buildToggleSettingCard(
                'Critical Alerts',
                'Notify when crowds exceed 7000 visitors',
                true,
              ),
              _buildToggleSettingCard(
                'High Alerts',
                'Notify when crowds exceed 5000 visitors',
                true,
              ),
              _buildToggleSettingCard(
                'Weather Warnings',
                'Notify on heavy rain (>20mm) or extreme heat (>35°C)',
                true,
              ),
            ],
          ),
          const SizedBox(height: 24),

          // Data Export Section
          _buildSettingSection(
            'Data Management',
            Icons.download,
            Colors.purple,
            [
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Material(
                  color: Colors.transparent,
                  child: InkWell(
                    onTap: () => _exportCrowdDataAsCSV(),
                    borderRadius: BorderRadius.circular(8),
                    child: Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.purple.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: Colors.purple.withOpacity(0.3)),
                      ),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Export Crowd Data',
                                style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                'Download forecast data as CSV',
                                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                  color: Colors.grey.shade600,
                                ),
                              ),
                            ],
                          ),
                          Icon(Icons.download, color: Colors.purple),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
              Material(
                color: Colors.transparent,
                child: InkWell(
                  onTap: () => _exportWeatherDataAsCSV(),
                  borderRadius: BorderRadius.circular(8),
                  child: Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.purple.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.purple.withOpacity(0.3)),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Export Weather Data',
                              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Download weather forecast as CSV',
                              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                color: Colors.grey.shade600,
                              ),
                            ),
                          ],
                        ),
                        Icon(Icons.download, color: Colors.purple),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 32),

          // About Section
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.grey.shade100,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'About This Dashboard',
                  style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  'This admin dashboard provides real-time crowd and weather forecasting for Sigiriya using advanced machine learning models.',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Colors.grey.shade700,
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  'Version 1.0 • Last Updated: 2024',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Colors.grey.shade600,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
        ],
      ),
    );
  }

  Widget _buildSettingSection(String title, IconData icon, Color color, List<Widget> children) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(icon, color: color, size: 24),
            const SizedBox(width: 8),
            Text(
              title,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
                color: color,
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        ...children,
      ],
    );
  }

  Widget _buildSettingCard(String title, String description, String value, IconData icon) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.grey.shade50,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(
                  title,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              Icon(icon, color: Colors.grey.shade600, size: 20),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            description,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Colors.grey.shade600,
            ),
          ),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: Colors.blue.withOpacity(0.1),
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(
              value,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Colors.blue.shade700,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildToggleSettingCard(String title, String description, bool defaultValue) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.grey.shade50,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  description,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Colors.grey.shade600,
                  ),
                ),
              ],
            ),
          ),
          Switch(
            value: defaultValue,
            onChanged: (_) {},
            activeColor: Colors.green,
          ),
        ],
      ),
    );
  }
}
