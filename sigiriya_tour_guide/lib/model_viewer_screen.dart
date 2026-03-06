import 'dart:math';
import 'dart:ui';
import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter_3d_controller/flutter_3d_controller.dart';


enum TimePreset { day, evening, night }

class ModelViewerScreen extends StatefulWidget {
  const ModelViewerScreen({super.key});

  @override
  State<ModelViewerScreen> createState() => _ModelViewerScreenState();
}

class _ModelViewerScreenState extends State<ModelViewerScreen>
    with TickerProviderStateMixin {
  final Flutter3DController controller = Flutter3DController();
  String srcGlb = 'assets/test.glb';

  bool isRaining = false;
  bool isFoggy = false;
  TimePreset preset = TimePreset.day;

  // Chat interface variables removed


  @override
  void initState() {
    super.initState();
    controller.onModelLoaded.addListener(() {
      debugPrint('model is loaded : ${controller.onModelLoaded.value}');
    });
  }



  BoxDecoration _backgroundForPreset() {
    switch (preset) {
      case TimePreset.day:
        return const BoxDecoration(
          gradient: RadialGradient(
            colors: [Color(0xffffffff), Colors.grey],
            stops: [0.1, 1.0],
            radius: 0.7,
            center: Alignment.center,
          ),
        );
      case TimePreset.evening:
        return const BoxDecoration(
          gradient: RadialGradient(
            colors: [Color(0xFFFFE0B2), Color(0xFF1B1F2A)],
            stops: [0.05, 1.0],
            radius: 0.9,
            center: Alignment.topCenter,
          ),
        );
      case TimePreset.night:
        return const BoxDecoration(
          gradient: RadialGradient(
            colors: [Color(0xFF1A237E), Color(0xFF05070D)],
            stops: [0.05, 1.0],
            radius: 1.0,
            center: Alignment.topCenter,
          ),
        );
    }
  }

  double _nightTintOpacity() {
    switch (preset) {
      case TimePreset.day:
        return 0.0;
      case TimePreset.evening:
        return 0.18;
      case TimePreset.night:
        return 0.35;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(

      body: Container(
        decoration: _backgroundForPreset(),
        width: double.infinity,
        height: double.infinity,
        child: Column(
          children: [
            Expanded(
              child: Stack(
                children: [
                  Flutter3DViewer(
                    activeGestureInterceptor: true,
                    progressBarColor: Colors.orange,
                    enableTouch: true,
                    onProgress: (p) =>
                        debugPrint('model loading progress : $p'),
                    onLoad: (modelAddress) {
                      debugPrint('model loaded : $modelAddress');
                      controller.setCameraOrbit(-85, 50, 5);
                      controller.playAnimation();
                    },
                    onError: (e) => debugPrint('model failed to load : $e'),
                    controller: controller,
                    src: srcGlb,
                  ),

                  // Night/Evening tint overlay
                  IgnorePointer(
                    child: AnimatedOpacity(
                      duration: const Duration(milliseconds: 300),
                      opacity: _nightTintOpacity(),
                      child: Container(color: Colors.black),
                    ),
                  ),

                  // Fog overlay (blur + haze)
                  IgnorePointer(child: FogOverlay(enabled: isFoggy)),

                  // Rain overlay (particles)
                  IgnorePointer(child: RainOverlay(enabled: isRaining)),
                ],
              ),
            ),

            // Controls panel
            Container(
              color: Colors.white,
              padding: const EdgeInsets.all(16),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    'Scene Controls',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 14),

                  ElevatedButton.icon(
                    onPressed: () => setState(() => isRaining = !isRaining),
                    icon: const Icon(Icons.water_drop),
                    label: Text(isRaining ? 'Disable Rain' : 'Enable Rain'),
                    style: ElevatedButton.styleFrom(
                      minimumSize: const Size(220, 50),
                    ),
                  ),
                  const SizedBox(height: 10),

                  ElevatedButton.icon(
                    onPressed: () => setState(() => isFoggy = !isFoggy),
                    icon: const Icon(Icons.cloud),
                    label: Text(isFoggy ? 'Disable Fog' : 'Enable Fog'),
                    style: ElevatedButton.styleFrom(
                      minimumSize: const Size(220, 50),
                    ),
                  ),
                  const SizedBox(height: 10),

                  ElevatedButton.icon(
                    onPressed: () {
                      setState(() {
                        preset = switch (preset) {
                          TimePreset.day => TimePreset.evening,
                          TimePreset.evening => TimePreset.night,
                          TimePreset.night => TimePreset.day,
                        };
                      });
                      debugPrint('Preset: $preset');
                    },
                    icon: const Icon(Icons.nightlight_round),
                    label: Text(switch (preset) {
                      TimePreset.day => 'Switch to Evening',
                      TimePreset.evening => 'Switch to Night',
                      TimePreset.night => 'Switch to Day',
                    }),
                    style: ElevatedButton.styleFrom(
                      minimumSize: const Size(220, 50),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class FogOverlay extends StatelessWidget {
  final bool enabled;
  const FogOverlay({super.key, required this.enabled});

  @override
  Widget build(BuildContext context) {
    return AnimatedOpacity(
      duration: const Duration(milliseconds: 350),
      opacity: enabled ? 1.0 : 0.0,
      child: BackdropFilter(
        filter: ImageFilter.blur(
          sigmaX: enabled ? 6 : 0,
          sigmaY: enabled ? 6 : 0,
        ),
        child: Container(
          color: Colors.white.withOpacity(0.10), // haze
        ),
      ),
    );
  }
}

class RainOverlay extends StatefulWidget {
  final bool enabled;
  const RainOverlay({super.key, required this.enabled});

  @override
  State<RainOverlay> createState() => _RainOverlayState();
}

class _RainOverlayState extends State<RainOverlay>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  final _rng = Random();
  late List<_Drop> _drops;

  @override
  void initState() {
    super.initState();
    _ctrl =
        AnimationController(
            vsync: this,
            duration: const Duration(milliseconds: 16),
          )
          ..addListener(() {
            if (!widget.enabled) return;
            setState(() {
              for (final d in _drops) {
                d.y += d.speed;
                if (d.y > 1.2) {
                  d.y = -0.2;
                  d.x = _rng.nextDouble();
                }
              }
            });
          })
          ..repeat();

    _drops = List.generate(220, (_) {
      return _Drop(
        x: _rng.nextDouble(),
        y: _rng.nextDouble(),
        len: _rng.nextDouble() * 0.04 + 0.02,
        speed: _rng.nextDouble() * 0.03 + 0.02,
      );
    });
  }

  @override
  void didUpdateWidget(covariant RainOverlay oldWidget) {
    super.didUpdateWidget(oldWidget);
    // keep controller running; we just stop drawing when disabled
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.enabled) return const SizedBox.shrink();
    return CustomPaint(painter: _RainPainter(_drops), size: Size.infinite);
  }
}

class _Drop {
  double x;
  double y;
  final double len;
  final double speed;

  _Drop({
    required this.x,
    required this.y,
    required this.len,
    required this.speed,
  });
}

class _RainPainter extends CustomPainter {
  final List<_Drop> drops;
  _RainPainter(this.drops);

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.lightBlueAccent.withOpacity(0.55)
      ..strokeWidth = 1.2
      ..strokeCap = StrokeCap.round;

    for (final d in drops) {
      final x = d.x * size.width;
      final y1 = d.y * size.height;
      final y2 = y1 + d.len * size.height;
      canvas.drawLine(Offset(x, y1), Offset(x, y2), paint);
    }
  }

  @override
  bool shouldRepaint(covariant _RainPainter oldDelegate) => true;
}


