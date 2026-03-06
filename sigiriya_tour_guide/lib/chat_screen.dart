import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:flutter_tts/flutter_tts.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen>
    with TickerProviderStateMixin {
  final TextEditingController _chatController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final List<ChatMessage> _messages = [];
  bool isApiHealthy = false;
  bool _isLoading = false;
  late AnimationController _headerAnimationController;
  late AnimationController _themeAnimationController;

  // Professional theme colors
  Color _currentPrimaryColor = const Color(0xFF2D3E50);  // Dark slate
  Color _currentAccentColor = const Color(0xFF3498DB);   // Professional blue
  Color _currentBgColor = const Color(0xFFFBFCFD);       // Almost white
  String _currentThemeType = 'default';

  // API URL: Use 10.0.2.2 for Android Emulator, localhost for web/desktop
  static const String apiBaseUrl = 'http://10.0.2.2:8000';

  // Quick suggestion buttons
  final List<String> _quickSuggestions = [
    '🌧️ Rain Forecast',
    '💨 Wind Today',
    '🌡️ Temperature',
    '👥 Crowd Levels',
    '📅 Best Days',
    '☀️ Sunny Days',
    '🌍 Weather Update',
    '✨ Recommendations',
  ];

  @override
  void initState() {
    super.initState();
    _checkApiHealth();
    _headerAnimationController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat(reverse: true);
    
    _themeAnimationController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    );

    // Add welcome message
    Future.delayed(const Duration(milliseconds: 500), () {
      if (mounted) {
        setState(() {
          _messages.add(
            ChatMessage(
              text:
                  '👋 Welcome to Sigiriya Digital Guide!\n\nI\'m here to help you explore the ancient rock fortress. Ask me anything about Sigiriya\'s history, attractions, or visitor information!',
              isUser: false,
              timestamp: DateTime.now(),
            ),
          );
        });
      }
    });
  }

  @override
  void dispose() {
    _chatController.dispose();
    _scrollController.dispose();
    _headerAnimationController.dispose();
    _themeAnimationController.dispose();
    super.dispose();
  }

  Future<void> _checkApiHealth() async {
    try {
      final response = await http
          .get(
            Uri.parse('$apiBaseUrl/health'),
            headers: {'accept': 'application/json'},
          )
          .timeout(const Duration(seconds: 5));

      if (mounted) {
        setState(() {
          isApiHealthy = response.statusCode == 200;
        });
      }
      debugPrint('API Health Check: ${isApiHealthy ? 'Healthy' : 'Unhealthy'}');
    } catch (e) {
      if (mounted) {
        setState(() {
          isApiHealthy = false;
        });
      }
      debugPrint('API Health Check Failed: $e');
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _sendMessage() async {
    if (_chatController.text.trim().isEmpty) return;

    final userMessage = _chatController.text;
    setState(() {
      _messages.add(
        ChatMessage(text: userMessage, isUser: true, timestamp: DateTime.now()),
      );
      _isLoading = true;
    });
    _chatController.clear();
    _scrollToBottom();

    try {
      debugPrint('Sending chat message to: $apiBaseUrl/chat');

      final response = await http
          .post(
            Uri.parse('$apiBaseUrl/chat'),
            headers: {'Content-Type': 'application/json'},
            body: json.encode({'message': userMessage}),
          )
          .timeout(const Duration(seconds: 30));

      String botResponse = '';
      List<DateTime>? bestDays;
      String? targetMonth;

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        botResponse = data['assistant_response'] ?? 'No response';
        
        // Extract best_days and target_month if available
        if (data['best_days'] != null && (data['best_days'] as List).isNotEmpty) {
          bestDays = [];
          targetMonth = data['target_month'];
          
          for (var dayData in data['best_days']) {
            try {
              final dateStr = dayData['date'];
              final parts = dateStr.split('-');
              if (parts.length == 3) {
                final year = int.parse(parts[0]);
                final month = int.parse(parts[1]);
                final day = int.parse(parts[2]);
                bestDays.add(DateTime(year, month, day));
              }
            } catch (e) {
              debugPrint('Error parsing best day date: $e');
            }
          }
        }
      } else {
        botResponse =
            'Error: Unable to get response (Status: ${response.statusCode})';
      }

      if (mounted) {
        setState(() {
          _messages.add(
            ChatMessage(
              text: botResponse,
              isUser: false,
              timestamp: DateTime.now(),
              bestDays: bestDays,
              targetMonth: targetMonth,
            ),
          );
          _isLoading = false;
        });
        _scrollToBottom();
        
        // Detect query type and apply theme
        _detectQueryTypeAndApplyTheme(userMessage, botResponse);
      }
    } catch (e) {
      debugPrint('Chat API Exception: $e');
      if (mounted) {
        setState(() {
          _messages.add(
            ChatMessage(
              text:
                  'Error: Could not connect to server.\nCheck if backend is running.',
              isUser: false,
              timestamp: DateTime.now(),
            ),
          );
          _isLoading = false;
        });
        _scrollToBottom();
      }
    }
  }

  void _detectQueryTypeAndApplyTheme(String userMessage, String botResponse) {
    final lowerMessage = userMessage.toLowerCase();
    
    // Rain theme - Professional blue
    if (lowerMessage.contains('rain')) {
      setState(() {
        _currentPrimaryColor = const Color(0xFF1E5A96);  // Dark professional blue
        _currentAccentColor = const Color(0xFF2E7CB8);   // Medium blue
        _currentThemeType = 'rain';
      });
      _showThemePopup('Rain Forecast', 'Rainfall expected. Bring an umbrella and waterproof gear.', const Color(0xFF2E7CB8), '🌧️');
    }
    // Wind theme - Professional teal
    else if (lowerMessage.contains('wind')) {
      setState(() {
        _currentPrimaryColor = const Color(0xFF0D6E7C);  // Dark teal
        _currentAccentColor = const Color(0xFF0F8F9E);   // Medium teal
        _currentThemeType = 'wind';
      });
      _showThemePopup('Wind Conditions', 'Strong winds detected. Wear light layers for comfort.', const Color(0xFF0F8F9E), '💨');
    }
    // Temperature theme - Professional warm orange
    else if (lowerMessage.contains('temperature') || lowerMessage.contains('hot') || lowerMessage.contains('temp')) {
      setState(() {
        _currentPrimaryColor = const Color(0xFF8B4513);  // Dark brown-orange
        _currentAccentColor = const Color(0xFFD2691E);   // Medium warm tone
        _currentThemeType = 'temperature';
      });
      _showThemePopup('High Temperature', 'Warm weather ahead. Stay hydrated and use sunscreen.', const Color(0xFFD2691E), '☀️');
    }
    // Crowd theme - Professional purple
    else if (lowerMessage.contains('crowd') || lowerMessage.contains('busy')) {
      setState(() {
        _currentPrimaryColor = const Color(0xFF5D3A6E);  // Dark purple
        _currentAccentColor = const Color(0xFF7B5A9F);   // Medium purple
        _currentThemeType = 'crowd';
      });
      _showThemePopup('Crowd Alert', 'High visitor numbers expected. Arrive early for better experience.', const Color(0xFF7B5A9F), '👥');
    }
    // Best days theme - Professional gold
    else if (lowerMessage.contains('best day')) {
      setState(() {
        _currentPrimaryColor = const Color(0xFF6B5414);  // Dark gold
        _currentAccentColor = const Color(0xFF9B8A30);   // Medium gold
        _currentThemeType = 'best_days';
      });
      _showThemePopup('Perfect Days', 'Ideal conditions for visiting with low crowds and great weather.', const Color(0xFF9B8A30), '✨');
    }
    // Weather update theme - Professional indigo
    else if (lowerMessage.contains('weather') || lowerMessage.contains('forecast')) {
      setState(() {
        _currentPrimaryColor = const Color(0xFF483D8B);  // Dark slate blue
        _currentAccentColor = const Color(0xFF6A5ACD);   // Medium slate blue
        _currentThemeType = 'weather';
      });
      _showThemePopup('Weather Update', 'Latest forecast received. Plan your visit accordingly.', const Color(0xFF6A5ACD), '🌈');
    }
  }

  void _showThemePopup(String title, String message, Color accentColor, String emoji) {
    Future.delayed(const Duration(milliseconds: 300), () {
      if (mounted) {
        showDialog(
          context: context,
          barrierColor: Colors.black.withOpacity(0.3),
          barrierDismissible: true,
          builder: (context) => Dialog(
            backgroundColor: Colors.transparent,
            elevation: 0,
            child: Container(
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: accentColor,
                  width: 2,
                ),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.1),
                    blurRadius: 12,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Clean header with left accent border
                  Container(
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      border: Border(
                        left: BorderSide(color: accentColor, width: 4),
                      ),
                    ),
                    child: Row(
                      children: [
                        Text(
                          emoji,
                          style: const TextStyle(fontSize: 32),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: Text(
                            title,
                            style: TextStyle(
                              color: accentColor,
                              fontWeight: FontWeight.w700,
                              fontSize: 16,
                              letterSpacing: 0.5,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  // Divider
                  Divider(
                    color: accentColor.withOpacity(0.2),
                    height: 1,
                  ),
                  // Content
                  Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          message,
                          style: const TextStyle(
                            fontSize: 14,
                            height: 1.6,
                            color: Color(0xFF2D3E50),
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                        const SizedBox(height: 16),
                        // Info indicator
                        Container(
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: accentColor.withOpacity(0.05),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(
                              color: accentColor.withOpacity(0.3),
                              width: 1,
                            ),
                          ),
                          child: Row(
                            children: [
                              Icon(
                                Icons.info_outline,
                                color: accentColor,
                                size: 16,
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  'Important information',
                                  style: TextStyle(
                                    color: accentColor,
                                    fontSize: 12,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                  // Action buttons
                  Padding(
                    padding: const EdgeInsets.only(
                      right: 20,
                      bottom: 16,
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.end,
                      children: [
                        TextButton(
                          onPressed: () => Navigator.pop(context),
                          style: TextButton.styleFrom(
                            foregroundColor: accentColor,
                            padding: const EdgeInsets.symmetric(
                              horizontal: 20,
                              vertical: 8,
                            ),
                          ),
                          child: const Text(
                            'Got it',
                            style: TextStyle(
                              fontWeight: FontWeight.w600,
                              fontSize: 13,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      }
    });
  }

  void _sendQuickMessage(String message) {
    _chatController.text = message.replaceAll(RegExp(r'[^\w\s]'), '').trim();
    _sendMessage();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: Stack(
        children: [
          // Beautiful gradient background
          Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  _currentBgColor.withOpacity(0.5),
                  _currentAccentColor.withOpacity(0.03),
                  Colors.white,
                ],
              ),
            ),
          ),
          // Decorative background elements
          Positioned(
            top: -50,
            right: -50,
            child: Container(
              width: 300,
              height: 300,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _currentAccentColor.withOpacity(0.05),
              ),
            ),
          ),
          Positioned(
            bottom: -80,
            left: -40,
            child: Container(
              width: 250,
              height: 250,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _currentPrimaryColor.withOpacity(0.03),
              ),
            ),
          ),
          // Background decoration icon
          Positioned(
            top: 120,
            right: -20,
            child: Icon(
              _getBackgroundIcon(),
              size: 180,
              color: _currentAccentColor.withOpacity(0.06),
            ),
          ),
          // Main content
          Column(
        children: [
          // Professional Header with Gradient
          Container(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  _currentPrimaryColor,
                  _currentAccentColor,
                  _currentAccentColor,
                ],
              ),
              boxShadow: [
                BoxShadow(
                  color: _currentAccentColor.withOpacity(0.25),
                  blurRadius: 20,
                  offset: const Offset(0, 8),
                  spreadRadius: 2,
                ),
              ],
            ),
            child: SafeArea(
              bottom: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 14, 16, 18),
                child: Row(
                  children: [
                    // Guide Avatar with Animation
                    Container(
                      padding: const EdgeInsets.all(2),
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: LinearGradient(
                          colors: isApiHealthy
                              ? [Colors.greenAccent, Colors.greenAccent.shade700]
                              : [Colors.redAccent, Colors.redAccent.shade700],
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: isApiHealthy
                                ? Colors.greenAccent.withOpacity(0.4)
                                : Colors.redAccent.withOpacity(0.4),
                            blurRadius: 8,
                            spreadRadius: 2,
                          ),
                        ],
                      ),
                      child: Container(
                        padding: const EdgeInsets.all(10),
                        decoration: const BoxDecoration(
                          color: Colors.white,
                          shape: BoxShape.circle,
                        ),
                        child: Icon(
                          Icons.support_agent_rounded,
                          color: _currentPrimaryColor,
                          size: 28,
                        ),
                      ),
                    ),
                    const SizedBox(width: 16),
                    // Guide Info
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'Sigiriya Guide',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 19,
                              fontWeight: FontWeight.w700,
                              letterSpacing: 0.3,
                            ),
                          ),
                          const SizedBox(height: 3),
                          Row(
                            children: [
                              Container(
                                width: 7,
                                height: 7,
                                decoration: BoxDecoration(
                                  color: isApiHealthy
                                      ? Colors.greenAccent
                                      : Colors.redAccent,
                                  shape: BoxShape.circle,
                                  boxShadow: [
                                    BoxShadow(
                                      color: isApiHealthy
                                          ? Colors.greenAccent.withOpacity(0.6)
                                          : Colors.redAccent.withOpacity(0.6),
                                      blurRadius: 6,
                                      spreadRadius: 1.5,
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(width: 8),
                              Text(
                                isApiHealthy
                                    ? 'Online & Ready'
                                    : 'Offline Mode',
                                style: TextStyle(
                                  color: Colors.white.withOpacity(0.85),
                                  fontSize: 12,
                                  fontWeight: FontWeight.w500,
                                  letterSpacing: 0.2,
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                    // Refresh Button with Enhanced Style
                    Container(
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.15),
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: Colors.white.withOpacity(0.2),
                          width: 1,
                        ),
                      ),
                      child: IconButton(
                        icon: const Icon(Icons.refresh_rounded, size: 22),
                        color: Colors.white,
                        onPressed: _checkApiHealth,
                        tooltip: 'Refresh Connection',
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),

          // Connection Status Banner (if offline)
          if (!isApiHealthy)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    Colors.orange.shade100,
                    Colors.orange.shade50,
                  ],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                border: Border(
                  bottom: BorderSide(
                    color: Colors.orange.shade300,
                    width: 2,
                  ),
                ),
                boxShadow: [
                  BoxShadow(
                    color: Colors.orange.withOpacity(0.1),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: Colors.orange[800]!.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Icon(
                      Icons.cloud_off_rounded,
                      color: Colors.orange[800],
                      size: 18,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Offline Mode',
                          style: TextStyle(
                            color: Colors.orange[900],
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 0.2,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          'Check your connection. Some features may be limited.',
                          style: TextStyle(
                            color: Colors.orange[800],
                            fontSize: 11,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 6,
                    ),
                    decoration: BoxDecoration(
                      color: Colors.orange[800]!.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(
                        color: Colors.orange[800]!.withOpacity(0.3),
                        width: 1,
                      ),
                    ),
                    child: GestureDetector(
                      onTap: _checkApiHealth,
                      child: Text(
                        'Retry',
                        style: TextStyle(
                          color: Colors.orange[800],
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),

          // Messages Area
          Expanded(
            child: _messages.isEmpty
                ? _buildEmptyState()
                : Column(
                    children: [
                      // Quick Suggestions (only show when few messages)
                      if (_messages.length <= 1) _buildQuickSuggestions(),

                      // Chat Messages
                      Expanded(
                        child: ListView.builder(
                          controller: _scrollController,
                          padding: const EdgeInsets.symmetric(
                            horizontal: 16,
                            vertical: 12,
                          ),
                          itemCount: _messages.length + (_isLoading ? 1 : 0),
                          itemBuilder: (context, index) {
                            if (index == _messages.length) {
                              return const _TypingIndicator();
                            }
                            return _ChatBubble(message: _messages[index]);
                          },
                        ),
                      ),
                    ],
                  ),
          ),

          // Message Input Area
          Container(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 20),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [
                  Colors.white,
                  _currentBgColor,
                ],
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
              ),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.06),
                  offset: const Offset(0, -2),
                  blurRadius: 12,
                  spreadRadius: 2,
                ),
              ],
              borderRadius: const BorderRadius.vertical(
                top: Radius.circular(28),
              ),
            ),
            child: SafeArea(
              child: Row(
                children: [
                  // Emoji/Tone Button
                  Container(
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        colors: [
                          Colors.purple.withOpacity(0.1),
                          Colors.pink.withOpacity(0.1),
                        ],
                      ),
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: Colors.purple.withOpacity(0.2),
                        width: 1,
                      ),
                    ),
                    child: IconButton(
                      icon: const Icon(Icons.emoji_emotions_outlined),
                      color: Colors.purple,
                      iconSize: 22,
                      onPressed: () {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Emoji picker coming soon!'),
                            duration: Duration(milliseconds: 1500),
                          ),
                        );
                      },
                      tooltip: 'Add emoji',
                    ),
                  ),
                  const SizedBox(width: 10),

                  // Text Input with Gradient border
                  Expanded(
                    child: Container(
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(20),
                        gradient: const LinearGradient(
                          colors: [
                            Color(0xFFEEEEEE),
                            Color(0xFFFAFAFA),
                          ],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                        border: Border.all(
                          color: _currentAccentColor.withOpacity(0.2),
                          width: 1.5,
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: _currentAccentColor.withOpacity(0.08),
                            blurRadius: 4,
                            offset: const Offset(0, 2),
                          ),
                        ],
                      ),
                      child: TextField(
                        controller: _chatController,
                        decoration: InputDecoration(
                          hintText: 'Ask about weather, crowds, best days...',
                          hintStyle: TextStyle(
                            color: Colors.grey[600],
                            fontSize: 14,
                            fontWeight: FontWeight.w400,
                          ),
                          border: InputBorder.none,
                          contentPadding: const EdgeInsets.symmetric(
                            horizontal: 18,
                            vertical: 12,
                          ),
                          isDense: true,
                        ),
                        textInputAction: TextInputAction.send,
                        onSubmitted: (_) => _sendMessage(),
                        maxLines: null,
                        style: const TextStyle(
                          color: Colors.black87,
                          fontSize: 15,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),

                  // Send Button with Enhanced Gradient
                  Container(
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                        colors: [
                          const Color(0xff0d2039),
                          Colors.teal.shade600,
                        ],
                      ),
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(
                          color: const Color(0xff0d2039).withOpacity(0.3),
                          blurRadius: 12,
                          offset: const Offset(0, 4),
                          spreadRadius: 1,
                        ),
                      ],
                    ),
                    child: Material(
                      color: Colors.transparent,
                      child: InkWell(
                        onTap: _sendMessage,
                        borderRadius: BorderRadius.circular(24),
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Icon(
                            _isLoading
                                ? Icons.hourglass_top_rounded
                                : Icons.send_rounded,
                            size: 20,
                            color: Colors.white,
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
        ],
      ),
    );
  }

  IconData _getBackgroundIcon() {
    switch (_currentThemeType) {
      case 'rain':
        return Icons.cloud_download_outlined;
      case 'wind':
        return Icons.air;
      case 'temperature':
        return Icons.sunny;
      case 'crowd':
        return Icons.people_outline;
      case 'best_days':
        return Icons.star_outline;
      case 'weather':
        return Icons.cloud_queue_outlined;
      default:
        return Icons.chat_bubble_outline;
    }
  }

  Widget _buildEmptyState() {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Main Icon with Gradient Background
            Stack(
              alignment: Alignment.center,
              children: [
                // Animated background circles
                Container(
                  width: 140,
                  height: 140,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [
                        const Color(0xff0d2039).withOpacity(0.08),
                        Colors.teal.withOpacity(0.08),
                      ],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    shape: BoxShape.circle,
                  ),
                ),
                Container(
                  padding: const EdgeInsets.all(32),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [
                        const Color(0xff0d2039).withOpacity(0.12),
                        Colors.teal.withOpacity(0.12),
                      ],
                    ),
                    shape: BoxShape.circle,
                  ),
                  child: Icon(
                    Icons.chat_bubble_outline_rounded,
                    size: 76,
                    color: const Color(0xff0d2039),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 32),
            
            // Welcome Title
            const Text(
              'Welcome to Sigiriya Guide',
              style: TextStyle(
                fontSize: 26,
                fontWeight: FontWeight.w800,
                color: Color(0xff0d2039),
                letterSpacing: 0.3,
              ),
            ),
            const SizedBox(height: 12),
            
            // Subtitle with emoji
            Text(
              'Your intelligent AI companion 🏔️\nfor exploring the ancient rock fortress',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 15,
                color: Colors.grey[700],
                height: 1.6,
                fontWeight: FontWeight.w500,
              ),
            ),
            const SizedBox(height: 28),
            
            // Features Box
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    Colors.blue.withOpacity(0.08),
                    Colors.teal.withOpacity(0.08),
                  ],
                ),
                borderRadius: BorderRadius.circular(14),
                border: Border.all(
                  color: Colors.teal.withOpacity(0.15),
                  width: 1.5,
                ),
              ),
              child: Column(
                children: [
                  _buildFeatureRow('🌧️', 'Weather forecasts'),
                  const SizedBox(height: 12),
                  _buildFeatureRow('👥', 'Crowd predictions'),
                  const SizedBox(height: 12),
                  _buildFeatureRow('📅', 'Best days to visit'),
                  const SizedBox(height: 12),
                  _buildFeatureRow('💬', 'Smart recommendations'),
                ],
              ),
            ),
            const SizedBox(height: 32),
            
            _buildQuickSuggestions(),
          ],
        ),
      ),
    );
  }

  Widget _buildFeatureRow(String emoji, String text) {
    return Row(
      children: [
        Text(emoji, style: const TextStyle(fontSize: 22)),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            text,
            style: const TextStyle(
              color: Colors.black87,
              fontSize: 14,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.2,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildQuickSuggestions() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: const Color(0xFF2E7CB8).withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                    color: const Color(0xFF2E7CB8).withOpacity(0.3),
                    width: 1,
                  ),
                ),
                child: const Icon(
                  Icons.lightbulb_outline,
                  size: 18,
                  color: Color(0xFF2E7CB8),
                ),
              ),
              const SizedBox(width: 12),
              const Text(
                'Ask me anything',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF2D3E50),
                  letterSpacing: 0.2,
                ),
              ),
            ],
          ),
        ),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Row(
            children: List.generate(_quickSuggestions.length, (index) {
              final colors = [
                Color(0xFF2E7CB8), // Blue
                Color(0xFF0F8F9E), // Teal
                Color(0xFFD2691E), // Orange
                Color(0xFF7B5A9F), // Purple
                Color(0xFF9B8A30), // Gold
                Color(0xFF4A7C5C), // Green
                Color(0xFF6A5ACD), // Indigo
                Color(0xFFC85A54), // Red
              ];
              
              return Padding(
                padding: const EdgeInsets.only(right: 10),
                child: Material(
                  color: Colors.transparent,
                  child: InkWell(
                    onTap: () => _sendQuickMessage(_quickSuggestions[index]),
                    borderRadius: BorderRadius.circular(8),
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 14,
                        vertical: 10,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: colors[index % colors.length],
                          width: 1.5,
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withOpacity(0.05),
                            blurRadius: 4,
                            offset: const Offset(0, 1),
                          ),
                        ],
                      ),
                      child: Text(
                        _quickSuggestions[index],
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: colors[index % colors.length],
                          letterSpacing: 0.2,
                        ),
                      ),
                    ),
                  ),
                ),
              );
            }),
          ),
        ),
        const SizedBox(height: 16),
      ],
    );
  }
}

class ChatMessage {
  final String text;
  final bool isUser;
  final DateTime timestamp;
  final List<DateTime>? bestDays; // Store best days data
  final String? targetMonth; // Store target month name

  ChatMessage({
    required this.text,
    required this.isUser,
    required this.timestamp,
    this.bestDays,
    this.targetMonth,
  });
}

class _ChatBubble extends StatefulWidget {
  final ChatMessage message;

  const _ChatBubble({required this.message});

  @override
  State<_ChatBubble> createState() => _ChatBubbleState();
}

class _ChatBubbleState extends State<_ChatBubble> {
  final FlutterTts _flutterTts = FlutterTts();
  bool _isSpeaking = false;

  @override
  void initState() {
    super.initState();
    _flutterTts.setCompletionHandler(() {
      if (mounted) setState(() => _isSpeaking = false);
    });
    _flutterTts.setCancelHandler(() {
      if (mounted) setState(() => _isSpeaking = false);
    });
  }

  @override
  void dispose() {
    _flutterTts.stop();
    super.dispose();
  }

  Future<void> _toggleSpeech() async {
    if (_isSpeaking) {
      await _flutterTts.stop();
      setState(() => _isSpeaking = false);
    } else {
      // Strip markdown formatting for cleaner reading
      final plainText = widget.message.text
          .replaceAll(RegExp(r'#+\s'), '')
          .replaceAll(RegExp(r'\*\*'), '')
          .replaceAll(RegExp(r'\*'), '')
          .replaceAll(RegExp(r'-\s+'), '')
          .replaceAll(RegExp(r'[\u{1F300}-\u{1FAFF}]', unicode: true), '')
          .trim();
      await _flutterTts.setSpeechRate(0.5);
      await _flutterTts.setLanguage('en-US');
      final result = await _flutterTts.speak(plainText);
      if (result == 1) setState(() => _isSpeaking = true);
    }
  }

  Widget _buildBestDaysCard(BuildContext context, String text, {List<DateTime>? bestDays, String? monthName}) {
    return Container(
      constraints: const BoxConstraints(maxWidth: 340),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: const Color(0xFF9B8A30),
          width: 2,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.08),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Clean header with left accent border
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              border: Border(
                left: BorderSide(
                  color: const Color(0xFF9B8A30),
                  width: 4,
                ),
              ),
            ),
            child: Row(
              children: [
                const Text(
                  '✨',
                  style: TextStyle(fontSize: 28),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Perfect Days to Visit',
                        style: TextStyle(
                          color: Color(0xFF6B5414),
                          fontWeight: FontWeight.w700,
                          fontSize: 15,
                          letterSpacing: 0.3,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        'Ideal conditions',
                        style: TextStyle(
                          color: const Color(0xFF6B5414).withOpacity(0.6),
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          // Divider
          Divider(
            color: const Color(0xFF9B8A30).withOpacity(0.2),
            height: 1,
          ),
          // Content
          Padding(
            padding: const EdgeInsets.all(16),
            child: Text(
              text,
              style: const TextStyle(
                color: Colors.black87,
                fontSize: 13,
                height: 1.6,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          // Stats Row
          Container(
            margin: const EdgeInsets.symmetric(horizontal: 16),
            padding: const EdgeInsets.symmetric(vertical: 12),
            decoration: BoxDecoration(
              color: const Color(0xFF9B8A30).withOpacity(0.05),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: const Color(0xFF9B8A30).withOpacity(0.2),
                width: 1,
              ),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _buildStatItem('👥', 'Low\nCrowd'),
                _buildStatItem('☀️', 'Great\nWeather'),
                _buildStatItem('🌳', 'Perfect\nDays'),
              ],
            ),
          ),
          // Action button
          Padding(
            padding: const EdgeInsets.all(16),
            child: SizedBox(
              width: double.infinity,
              child: TextButton(
                onPressed: () {
                  showDialog(
                    context: context,
                    builder: (dialogContext) => CalendarViewDialog(
                      bestDays: bestDays ?? [],
                      monthName: monthName,
                    ),
                  );
                },
                style: TextButton.styleFrom(
                  foregroundColor: const Color(0xFF6B5414),
                  side: const BorderSide(
                    color: Color(0xFF9B8A30),
                    width: 1.5,
                  ),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                  padding: const EdgeInsets.symmetric(vertical: 10),
                ),
                child: const Text(
                  '📅 View Calendar',
                  style: TextStyle(
                    fontWeight: FontWeight.w600,
                    fontSize: 13,
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHourlyWeatherCard(BuildContext context, String text) {
    // Extract hourly weather data from response text
    
    return Container(
      constraints: const BoxConstraints(maxWidth: 320),
      margin: const EdgeInsets.symmetric(vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: const Color(0xFF2E7CB8),
          width: 2,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.08),
            blurRadius: 8,
            offset: const Offset(0, 3),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          // Header with blue accent
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: const Color(0xFF2E7CB8).withOpacity(0.1),
              border: const Border(
                bottom: BorderSide(
                  color: Color(0xFF2E7CB8),
                  width: 2,
                ),
              ),
            ),
            child: Row(
              children: const [
                Icon(Icons.access_time_rounded, color: Color(0xFF2E7CB8), size: 20),
                SizedBox(width: 8),
                Text(
                  '🕐 Real-Time Hourly Weather',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF2E7CB8),
                  ),
                ),
              ],
            ),
          ),
          // Content
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: _buildHourlyItems(text),
              ),
            ),
          ),
          // Footer info
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: const Color(0xFF2E7CB8).withOpacity(0.05),
              border: const Border(
                top: BorderSide(
                  color: Color(0xFF2E7CB8),
                  width: 1,
                ),
              ),
            ),
            child: const Text(
              '📍 Sigiriya, Sri Lanka | 📊 OpenWeatherMap (Real-time)',
              style: TextStyle(
                fontSize: 11,
                color: Color(0xFF666666),
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }

  List<Widget> _buildHourlyItems(String text) {
    // Parse the hourly weather text and create card items
    final items = <Widget>[];
    final lines = text.split('\n');
    
    // Extract hourly data blocks (each hour starts with ⏰)
    int hourCount = 0;
    for (int i = 0; i < lines.length && hourCount < 4; i++) {
      if (lines[i].contains('⏰')) {
        final timeMatch = RegExp(r'⏰\s+([^*]+)').firstMatch(lines[i]);
        if (timeMatch != null && i + 5 < lines.length) {
          final time = timeMatch.group(1)?.trim() ?? '';
          final tempLine = lines[i + 1];
          final rainfallLine = lines[i + 3];
          
          final tempEmoji = tempLine.contains('🌡️') ? '🌡️' : '☀️';
          final tempValue = RegExp(r'(\d+\.?\d*)°C').firstMatch(tempLine)?.group(1) ?? '';
          const Color itemColor = Color(0xFF2E7CB8);
          
          items.add(
            Container(
              width: 70,
              margin: const EdgeInsets.only(right: 8),
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                border: Border.all(
                  color: itemColor.withOpacity(0.6),
                  width: 1.5,
                ),
                borderRadius: BorderRadius.circular(8),
                color: Colors.white,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    time,
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                      color: Color(0xFF2E7CB8),
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 6),
                  Text(
                    '$tempEmoji $tempValue°C',
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: Colors.black87,
                    ),
                  ),
                  const SizedBox(height: 4),
                  if (rainfallLine.contains('☔') || rainfallLine.contains('✅'))
                    Text(
                      rainfallLine.contains('✅') ? '✅ No Rain' : '☔ Rain',
                      style: const TextStyle(
                        fontSize: 10,
                        color: Colors.grey,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                ],
              ),
            ),
          );
          hourCount++;
          i += 5;
        }
      }
    }
    
    return items.isNotEmpty
        ? items
        : [
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Text(
                  text,
                  style: const TextStyle(
                    color: Colors.black87,
                    fontSize: 13,
                    height: 1.6,
                  ),
                ),
              ),
            ),
          ];
  }

  Widget _buildStatItem(String emoji, String label) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          emoji,
          style: const TextStyle(fontSize: 24),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          textAlign: TextAlign.center,
          style: const TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w600,
            color: Color(0xFF92400E),
            height: 1.3,
          ),
        ),
      ],
    );
  }

  Widget _buildRichText(String text, {bool isUser = false, Color? color}) {
    // Parse text for formatting: **bold**, *italic*, etc.
    return Text(
      text,
      style: TextStyle(
        color: color ?? (isUser ? Colors.white : Colors.black87),
        fontSize: 15,
        height: 1.6,
        letterSpacing: 0.2,
        fontWeight: isUser ? FontWeight.w600 : FontWeight.w500,
      ),
    );
  }

  String _formatTime(DateTime time) {
    final hour = time.hour > 12
        ? time.hour - 12
        : (time.hour == 0 ? 12 : time.hour);
    final minute = time.minute.toString().padLeft(2, '0');
    final period = time.hour >= 12 ? 'PM' : 'AM';
    return '$hour:$minute $period';
  }

  @override
  Widget build(BuildContext context) {
    final message = widget.message;
    // Check if message contains best days info
    bool isBestDaysMessage = message.text.toLowerCase().contains('best') &&
        (message.text.toLowerCase().contains('day') ||
            message.text.toLowerCase().contains('visit'));
    
    // Check if message is hourly weather (real-time)
    bool isHourlyWeatherMessage = message.text.toLowerCase().contains('hourly') &&
        message.text.toLowerCase().contains('weather') &&
        message.text.toLowerCase().contains('sigiriya');

    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Row(
        mainAxisAlignment: message.isUser
            ? MainAxisAlignment.end
            : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          // Guide Avatar (for bot messages) - simplified
          if (!message.isUser) ...[
            Container(
              width: 36,
              height: 36,
              margin: const EdgeInsets.only(right: 10, bottom: 4),
              decoration: BoxDecoration(
                color: const Color(0xFF2E7CB8),
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.1),
                    blurRadius: 6,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: const Icon(
                Icons.support_agent_rounded,
                color: Colors.white,
                size: 18,
              ),
            ),
          ],

          // Message Bubble - Beautiful modern design
          Flexible(
            child: isBestDaysMessage && !message.isUser
                ? _buildBestDaysCard(
                    context,
                    message.text,
                    bestDays: message.bestDays,
                    monthName: message.targetMonth,
                  )
                : isHourlyWeatherMessage && !message.isUser
                    ? _buildHourlyWeatherCard(context, message.text)
                    : Container(
                    constraints: const BoxConstraints(maxWidth: 300),
                    padding:
                        const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    decoration: BoxDecoration(
                      color: message.isUser 
                          ? const Color(0xFF2E7CB8)
                          : Colors.white,
                      borderRadius: BorderRadius.only(
                        topLeft: const Radius.circular(16),
                        topRight: const Radius.circular(16),
                        bottomLeft:
                            Radius.circular(message.isUser ? 16 : 4),
                        bottomRight:
                            Radius.circular(message.isUser ? 4 : 16),
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withOpacity(0.08),
                          blurRadius: 8,
                          offset: const Offset(0, 2),
                          spreadRadius: 1,
                        ),
                      ],
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _buildRichText(
                          message.text,
                          isUser: message.isUser,
                          color: message.isUser ? Colors.white : Colors.black87,
                        ),
                        const SizedBox(height: 6),
                        Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(
                              Icons.access_time_rounded,
                              size: 10,
                              color: message.isUser 
                                  ? Colors.white.withOpacity(0.7)
                                  : Colors.grey[500],
                            ),
                            const SizedBox(width: 4),
                            Text(
                              _formatTime(message.timestamp),
                              style: TextStyle(
                                color: message.isUser 
                                    ? Colors.white.withOpacity(0.7)
                                    : Colors.grey[500],
                                fontSize: 11,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                            if (message.isUser) ...[
                              const SizedBox(width: 6),
                              Icon(
                                Icons.done_all_rounded,
                                size: 11,
                                color: Colors.white.withOpacity(0.8),
                              ),
                            ],
                          ],
                        ),
                      ],
                    ),
                  ),
          ),

          // Speaker button for bot messages
          if (!message.isUser) ...[
            const SizedBox(width: 8),
            GestureDetector(
              onTap: _toggleSpeech,
              child: Container(
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(
                  color: _isSpeaking
                      ? const Color(0xFF2E7CB8).withOpacity(0.15)
                      : Colors.grey.shade100,
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: _isSpeaking
                        ? const Color(0xFF2E7CB8)
                        : Colors.grey.shade300,
                    width: 1,
                  ),
                ),
                child: Icon(
                  _isSpeaking ? Icons.stop_rounded : Icons.volume_up_rounded,
                  size: 16,
                  color: _isSpeaking
                      ? const Color(0xFF2E7CB8)
                      : Colors.grey.shade500,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}


class _TypingIndicator extends StatelessWidget {
  const _TypingIndicator();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          // Guide Avatar with simple color
          Container(
            width: 32,
            height: 32,
            margin: const EdgeInsets.only(right: 8, bottom: 4),
            decoration: BoxDecoration(
              color: const Color(0xFF2E7CB8),
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.1),
                  blurRadius: 6,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: const Icon(
              Icons.support_agent_rounded,
              color: Colors.white,
              size: 16,
            ),
          ),

          // Typing Bubble - Clean simple design
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(12),
                topRight: Radius.circular(12),
                bottomLeft: Radius.circular(3),
                bottomRight: Radius.circular(12),
              ),
              border: Border.all(
                color: Colors.grey[300]!,
                width: 1.2,
              ),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.05),
                  blurRadius: 6,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const _Dot(delay: 0),
                const SizedBox(width: 5),
                const _Dot(delay: 1),
                const SizedBox(width: 5),
                const _Dot(delay: 2),
                const SizedBox(width: 8),
                Text(
                  'thinking...',
                  style: TextStyle(
                    color: Colors.grey[500],
                    fontSize: 11,
                    fontStyle: FontStyle.italic,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Dot extends StatefulWidget {
  final int delay;
  const _Dot({required this.delay});

  @override
  State<_Dot> createState() => _DotState();
}

class _DotState extends State<_Dot> with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ScaleTransition(
      scale: Tween(begin: 0.5, end: 1.0).animate(
        CurvedAnimation(
          parent: _controller,
          curve: Interval(widget.delay * 0.2, 1.0, curve: Curves.easeInOut),
        ),
      ),
      child: Container(
        width: 8,
        height: 8,
        decoration: BoxDecoration(
          color: const Color(0xFF2E7CB8),
          shape: BoxShape.circle,
        ),
      ),
    );
  }
}
// Calendar View Dialog for Best Days
class CalendarViewDialog extends StatefulWidget {
  final List<DateTime> bestDays;
  final String? monthName;

  const CalendarViewDialog({
    required this.bestDays,
    this.monthName,
    Key? key,
  }) : super(key: key);

  @override
  State<CalendarViewDialog> createState() => _CalendarViewDialogState();
}

class _CalendarViewDialogState extends State<CalendarViewDialog> {
  late DateTime displayMonth;

  @override
  void initState() {
    super.initState();
    if (widget.bestDays.isNotEmpty) {
      displayMonth = widget.bestDays[0];
    } else {
      // Show current month with some sample best days for demonstration
      displayMonth = DateTime.now();
      // Add sample best days if none provided
      if (widget.bestDays.isEmpty) {
        final now = DateTime.now();
        widget.bestDays.addAll([
          DateTime(now.year, now.month, 5),
          DateTime(now.year, now.month, 10),
          DateTime(now.year, now.month, 15),
          DateTime(now.year, now.month, 20),
          DateTime(now.year, now.month, 25),
        ]);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      insetPadding: const EdgeInsets.all(16),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
      child: Container(
        color: Colors.white,
        child: SingleChildScrollView(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Header - Clean professional style
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      'Best Days to Visit',
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w700,
                        color: Color(0xFF2D3E50),
                      ),
                    ),
                    GestureDetector(
                      onTap: () => Navigator.pop(context),
                      child: Container(
                        padding: const EdgeInsets.all(4),
                        decoration: BoxDecoration(
                          color: Colors.grey[100],
                          shape: BoxShape.circle,
                        ),
                        child: Icon(
                          Icons.close,
                          size: 20,
                          color: Colors.grey.shade600,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 20),
                // Month/Year header - Professional outline
                Container(
                  padding: const EdgeInsets.symmetric(
                    vertical: 14,
                    horizontal: 16,
                  ),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                      color: const Color(0xFF9B8A30),
                      width: 2,
                    ),
                  ),
                  child: Text(
                    displayMonth.toString().split(' ')[0] == '' 
                      ? widget.monthName ?? displayMonth.toString().split(' ')[0]
                      : '${_getMonthName(displayMonth.month)} ${displayMonth.year}',
                    style: const TextStyle(
                      color: Color(0xFF6B5414),
                      fontSize: 16,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.3,
                    ),
                    textAlign: TextAlign.center,
                  ),
                ),
                const SizedBox(height: 20),
                // Calendar Grid
                _buildCalendarGrid(),
                const SizedBox(height: 20),
                // Legend
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: const Color(0xFF9B8A30).withOpacity(0.05),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                      color: const Color(0xFF9B8A30).withOpacity(0.3),
                      width: 1.5,
                    ),
                  ),
                  child: Column(
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          _buildLegendItem(
                            Colors.green,
                            'Best Days',
                          ),
                          const SizedBox(width: 24),
                          _buildLegendItem(
                            Colors.grey.shade300,
                            'Other Days',
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Text(
                        '🌟 Green dates: excellent weather & manageable crowds',
                        style: TextStyle(
                          color: Colors.grey[700],
                          fontSize: 11,
                          fontStyle: FontStyle.italic,
                          fontWeight: FontWeight.w500,
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 18),
                // Close Button - Professional outline
                SizedBox(
                  width: double.infinity,
                  child: TextButton(
                    onPressed: () => Navigator.pop(context),
                    style: TextButton.styleFrom(
                      foregroundColor: const Color(0xFF6B5414),
                      side: const BorderSide(
                        color: Color(0xFF9B8A30),
                        width: 1.5,
                      ),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10),
                      ),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                    child: const Text(
                      'Got it',
                      style: TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 14,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildCalendarGrid() {
    List<String> weekDays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    
    // Get first day of month
    DateTime firstDay = DateTime(displayMonth.year, displayMonth.month, 1);
    int daysInMonth = DateTime(displayMonth.year, displayMonth.month + 1, 0).day;
    int startingWeekday = firstDay.weekday % 7;
    
    List<Widget> dayWidgets = [];
    
    // Week day headers
    for (String day in weekDays) {
      dayWidgets.add(
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Text(
            day,
            textAlign: TextAlign.center,
            style: TextStyle(
              fontWeight: FontWeight.w700,
              color: Colors.grey.shade700,
              fontSize: 12,
            ),
          ),
        ),
      );
    }
    
    // Empty cells before month starts
    for (int i = 0; i < startingWeekday; i++) {
      dayWidgets.add(const SizedBox.shrink());
    }
    
    // Days of month
    for (int day = 1; day <= daysInMonth; day++) {
      DateTime date = DateTime(displayMonth.year, displayMonth.month, day);
      bool isBestDay = widget.bestDays.any(
        (d) => d.year == date.year && d.month == date.month && d.day == date.day,
      );
      
      dayWidgets.add(
        Container(
          margin: const EdgeInsets.all(4),
          decoration: BoxDecoration(
            color: isBestDay ? Colors.green.shade400 : Colors.grey.shade100,
            borderRadius: BorderRadius.circular(8),
            border: isBestDay
              ? Border.all(
                  color: Colors.green.shade600,
                  width: 2,
                )
              : null,
            boxShadow: isBestDay
              ? [
                  BoxShadow(
                    color: Colors.green.shade400.withOpacity(0.4),
                    blurRadius: 6,
                    offset: const Offset(0, 2),
                  ),
                ]
              : null,
          ),
          child: Center(
            child: Text(
              '$day',
              style: TextStyle(
                color: isBestDay ? Colors.white : Colors.grey.shade700,
                fontWeight: isBestDay ? FontWeight.w700 : FontWeight.w500,
                fontSize: 14,
              ),
            ),
          ),
        ),
      );
    }
    
    return GridView.count(
      crossAxisCount: 7,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      childAspectRatio: 1.2,
      children: dayWidgets,
    );
  }

  Widget _buildLegendItem(Color color, String label) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 20,
          height: 20,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(4),
            border: Border.all(
              color: color == Colors.green
                ? Colors.green.shade600
                : Colors.grey.shade400,
              width: 1.5,
            ),
          ),
        ),
        const SizedBox(width: 8),
        Text(
          label,
          style: TextStyle(
            color: Colors.grey.shade800,
            fontWeight: FontWeight.w600,
            fontSize: 13,
          ),
        ),
      ],
    );
  }

  String _getMonthName(int month) {
    const months = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December'
    ];
    return months[month - 1];
  }
}