#pragma once
#include <Arduino.h>
#include <Preferences.h>
#include <WebServer.h>
#include "runtime_policy.h"

class NetworkSetup {
 public:
  void begin();
  void tick();
 private:
  const IPAddress apIP_{192, 168, 4, 1};
  WebServer portal_{IPAddress(192, 168, 4, 1), 80};
  Preferences preferences_;
  apc::Policy policy_;
  apc::BootButton button_;
  apc::Credentials saved_, candidate_;
  bool storageReady_ = false, cameraReady_ = false, portalActive_ = false;
  bool pendingConnect_ = false, pendingForget_ = false, mdnsActive_ = false;
  bool cameraServing_ = false;
  uint32_t requestAt_ = 0, retryCameraAt_ = 0;
  String csrfToken_;

  void apply(apc::Action action);
  void connectSaved();
  void startSetup();
  void stopPortal();
  void stopVideo();
  bool forget();
  bool allowed(bool mutation = false);
  void reply(int code, const String &body, const char *type = "text/html; charset=utf-8");
  void showPortal();
  void scanNetworks();
  void saveRequest();
  void forgetRequest();
};
