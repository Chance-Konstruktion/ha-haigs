"""Tests der Home-Assistant-Bahn (M2).

Getrennt von ``tests/``: hierfuer ist Home Assistant installiert
(siehe requirements-ha.txt und den CI-Job ``tests-homeassistant``),
dort laeuft die schlanke Kern-Suite ohne. Dass dieses Verzeichnis ein
Paket ist, ist Absicht -- pytest setzt dadurch den Wurzelordner auf
den Importpfad, und sowohl ``haigs`` als auch ``custom_components``
sind auffindbar.
"""
