import 'package:flutter/material.dart';
import 'package:presenca_box/views/faceRecognition.dart';
import 'package:firebase_core/firebase_core.dart';

import 'firebase_options.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: "Face Recognition app",
      debugShowCheckedModeBanner: false,
      home: FaceRecognition(),
    );
  }
}

