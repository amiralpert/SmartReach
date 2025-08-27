// ======================
// DOGNOSIS OUTREACH AUTOMATION - MAIN ENTRY POINT
// The ONLY file users need to interact with
// ======================

const Main = {
  // ====================
  // USER COMMANDS - Only 4 functions users ever need to remember
  // ====================
  
  /**
   * Complete setup process - from zero to ready
   * Automatically detects and fixes common issues
   */
  setup: function() {
    console.log("🚀 DOGNOSIS SETUP - Starting complete configuration...");
    
    try {
      // Auto-fix any existing issues first
      AutoFix.detectAndFixColumnMismatches();
      
      // Run complete setup
      const result = Setup.runInitialConfig();
      
      if (result.success) {
        console.log("✅ Setup complete! Ready for testing.");
        console.log("💡 Next step: Run Main.test()");
      } else {
        console.log("❌ Setup encountered issues - auto-fixing...");
        AutoFix.selfDiagnoseAndRepair();
        
        // Retry setup
        const retryResult = Setup.runInitialConfig();
        if (retryResult.success) {
          console.log("✅ Setup complete after auto-fix!");
        } else {
          console.log("🚨 Manual intervention required. Check error logs.");
        }
      }
      
      return result;
      
    } catch (error) {
      console.log(`💥 Setup error: ${error.toString()}`);
      console.log("🔧 Attempting auto-repair...");
      AutoFix.selfDiagnoseAndRepair();
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Test system with your contacts - fast and comprehensive
   * Uses intelligent testing to validate all components
   */
  test: function() {
    console.log("🧪 DOGNOSIS TEST - Running comprehensive system test...");
    
    try {
      // Pre-test system validation
      const systemCheck = Test.runSystemCheck();
      if (!systemCheck.success) {
        console.log("⚠️ System issues detected - auto-fixing before test...");
        AutoFix.selfDiagnoseAndRepair();
      }
      
      // Run fast-forward live test
      const testResult = Test.runFastForward();
      
      if (testResult.success) {
        console.log("✅ All tests passed! System is ready for live deployment.");
        console.log("💡 Next step: Run Main.go() to start automation");
      } else {
        console.log("⚠️ Some tests failed - reviewing results...");
        Monitor.getTestReport();
      }
      
      return testResult;
      
    } catch (error) {
      console.log(`💥 Test error: ${error.toString()}`);
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Start live automation - intelligent and self-managing
   * System runs completely autonomously with smart optimization
   */
  go: function() {
    console.log("🔥 DOGNOSIS GO LIVE - Starting intelligent automation...");
    
    try {
      // Final pre-flight checks
      const healthCheck = Monitor.getSystemHealth();
      if (!healthCheck.healthy) {
        console.log("🔧 Pre-flight issues detected - auto-fixing...");
        AutoFix.selfDiagnoseAndRepair();
      }
      
      // Start intelligent automation
      const automationResult = Orchestrator.runIntelligentAutomation();
      
      if (automationResult.success) {
        console.log("🎉 AUTOMATION IS LIVE!");
        console.log("📊 Monitor progress with Main.monitor()");
        console.log("🧠 System will optimize itself automatically");
      } else {
        console.log("❌ Failed to start automation - check system status");
        Monitor.getSystemHealth();
      }
      
      return automationResult;
      
    } catch (error) {
      console.log(`💥 Go-live error: ${error.toString()}`);
      return { success: false, error: error.toString() };
    }
  },
  
  /**
   * Monitor system performance and get insights
   * Shows real-time stats and intelligent recommendations
   */
  monitor: function() {
    console.log("📊 DOGNOSIS MONITOR - Fetching system insights...");
    
    try {
      // Get comprehensive system status
      const status = Monitor.getComprehensiveStatus();
      const insights = Intelligence.getPerformanceInsights();
      const recommendations = Intelligence.getOptimizationRecommendations();
      
      console.log("=" .repeat(60));
      console.log("📈 SYSTEM PERFORMANCE DASHBOARD");
      console.log("=" .repeat(60));
      
      // Display key metrics
      console.log(`📧 Emails sent today: ${status.emailsSentToday}`);
      console.log(`🤝 LinkedIn connects today: ${status.linkedinConnectsToday}`);
      console.log(`💬 LinkedIn messages today: ${status.linkedinMessagesToday}`);
      console.log(`📞 Replies received: ${status.repliesReceived}`);
      console.log(`📈 Response rate: ${status.responseRate}%`);
      
      // Show intelligent insights
      if (insights.length > 0) {
        console.log("\n🧠 INTELLIGENT INSIGHTS:");
        insights.forEach(insight => console.log(`   • ${insight}`));
      }
      
      // Show recommendations
      if (recommendations.length > 0) {
        console.log("\n💡 OPTIMIZATION RECOMMENDATIONS:");
        recommendations.forEach(rec => console.log(`   • ${rec}`));
      }
      
      return { status, insights, recommendations };
      
    } catch (error) {
      console.log(`💥 Monitor error: ${error.toString()}`);
      return { success: false, error: error.toString() };
    }
  },
  
  // ====================
  // QUICK ACCESS FUNCTIONS - For power users
  // ====================
  
  /**
   * Emergency stop - immediately pause all automation
   */
  stop: function() {
    console.log("🛑 EMERGENCY STOP - Pausing all automation...");
    return Orchestrator.emergencyStop();
  },
  
  /**
   * Quick health check - is everything working?
   */
  health: function() {
    console.log("🏥 HEALTH CHECK - Checking system status...");
    return Monitor.getSystemHealth();
  },
  
  /**
   * Quick fix - automatically resolve common issues
   */
  fix: function() {
    console.log("🔧 AUTO-FIX - Resolving system issues...");
    return AutoFix.selfDiagnoseAndRepair();
  },
  
  /**
   * Show help and next steps
   */
  help: function() {
    console.log("\n🎯 DOGNOSIS AUTOMATION - QUICK START GUIDE");
    console.log("=" .repeat(50));
    console.log("1️⃣  Main.setup()   - Configure system");
    console.log("2️⃣  Main.test()    - Test with your contacts"); 
    console.log("3️⃣  Main.go()      - Start live automation");
    console.log("4️⃣  Main.monitor() - Check performance");
    console.log("");
    console.log("🚨 Emergency commands:");
    console.log("🛑  Main.stop()    - Emergency stop");
    console.log("🏥  Main.health()  - Health check");
    console.log("🔧  Main.fix()     - Auto-fix issues");
    console.log("");
    console.log("💡 That's it! Just 4 main commands to remember.");
    console.log("   System handles everything else automatically.");
  }
};

// Auto-show help on load
console.log("✅ Dognosis Automation loaded! (v2.0 - Streamlined)");
console.log("💡 Type Main.help() to see available commands");
console.log("🚀 Quick start: Main.setup() → Main.test() → Main.go()");