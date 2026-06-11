const defaultApiBase = "http://127.0.0.1:8000";

App({
  onLaunch() {
    const savedApiBase = wx.getStorageSync("foodnote_api_base");
    if (savedApiBase) {
      this.globalData.apiBase = savedApiBase;
    }
  },

  globalData: {
    apiBase: defaultApiBase
  }
});
