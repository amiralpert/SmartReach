// ======================
// DOGNOSIS OUTREACH AUTOMATION - MONITOR DOMAIN
// System monitoring, stats, and health checks
// ======================

const Monitor = {
  /**
   * Get comprehensive system status and performance metrics
   */
  getComprehensiveStatus: function() {
    console.log("📊 Gathering comprehensive system status...");
    
    try {
      const status = {
        timestamp: new Date(),
        system: this.getSystemHealth(),
        performance: this.getPerformanceMetrics(),
        campaign: this.getCampaignStatus(),
        errors: this.getRecentErrors()
      };
      
      return status;
      
    } catch (error) {
      console.log(`Error getting system status: ${error.toString()}`);
      return { error: error.toString() };
    }
  },
  
  /**
   * Get system health status
   */
  getSystemHealth: function() {
    const health = {
      healthy: true,
      components: [],
      issues: []
    };
    
    try {
      // Check Gmail quota
      const gmailQuota = MailApp.getRemainingDailyQuota();
      health.components.push({
        name: "Gmail",
        status: gmailQuota > VALIDATION.MIN_GMAIL_QUOTA ? "healthy" : "warning",
        details: `${gmailQuota} emails remaining today`,
        quota: gmailQuota
      });
      
      if (gmailQuota < VALIDATION.MIN_GMAIL_QUOTA) {
        health.issues.push("Low Gmail quota");
        health.healthy = false;
      }
      
      // Check PhantomBuster config
      const pbConfig = Services.getProperty('phantombuster_config');
      health.components.push({
        name: "PhantomBuster",
        status: pbConfig ? "healthy" : "error",
        details: pbConfig ? "Configured and ready" : "Not configured",
        configured: !!pbConfig
      });
      
      if (!pbConfig) {
        health.issues.push("PhantomBuster not configured");
        health.healthy = false;
      }
      
      // Check spreadsheet access
      try {
        const ss = SpreadsheetApp.getActiveSpreadsheet();
        const contactSheet = ss.getSheetByName("ContactList");
        const contactCount = contactSheet ? contactSheet.getLastRow() - 1 : 0;
        
        health.components.push({
          name: "Spreadsheet",
          status: contactCount > 0 ? "healthy" : "warning",
          details: `${contactCount} contacts in ContactList`,
          contactCount: contactCount
        });
        
        if (contactCount === 0) {
          health.issues.push("No contacts in ContactList");
          health.healthy = false;
        }
        
      } catch (e) {
        health.components.push({
          name: "Spreadsheet",
          status: "error", 
          details: "Access error"
        });
        health.issues.push("Spreadsheet access error");
        health.healthy = false;
      }
      
      // Check automation triggers
      const triggers = ScriptApp.getProjectTriggers();
      const automationTrigger = triggers.find(t => 
        t.getHandlerFunction().includes('runDailyAutomation') ||
        t.getHandlerFunction().includes('runCompleteAutomation')
      );
      
      health.components.push({
        name: "Automation",
        status: automationTrigger ? "healthy" : "warning",
        details: automationTrigger ? "Daily triggers active" : "No automation triggers",
        triggersActive: !!automationTrigger
      });
      
      if (!automationTrigger) {
        health.issues.push("No automation triggers active");
      }
      
      return health;
      
    } catch (error) {
      return {
        healthy: false,
        error: error.toString(),
        components: [],
        issues: ["System health check failed"]
      };
    }
  },
  
  /**
   * Get performance metrics
   */
  getPerformanceMetrics: function() {
    const metrics = {
      today: this.getTodayMetrics(),
      thisWeek: this.getWeekMetrics(), 
      allTime: this.getAllTimeMetrics()
    };
    
    return metrics;
  },
  
  /**
   * Get today's performance metrics
   */
  getTodayMetrics: function() {
    try {
      const today = new Date();
      const todayStr = Utilities.formatDate(today, Session.getScriptTimeZone(), 'MM/dd/yyyy');
      
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      const data = contactSheet.getDataRange().getValues();
      const headers = data[0];
      
      let emailsSent = 0;
      let linkedinConnects = 0;
      let linkedinMessages = 0;
      let repliesReceived = 0;
      
      // Count activities from tracking columns
      for (let i = 1; i < data.length; i++) {
        const row = data[i];
        
        // Count emails sent today
        for (let j = 0; j < headers.length; j++) {
          const header = headers[j];
          const value = row[j];
          
          if (header.includes("Email Sent") && value) {
            const dateValue = new Date(value);
            if (Utilities.formatDate(dateValue, Session.getScriptTimeZone(), 'MM/dd/yyyy') === todayStr) {
              emailsSent++;
            }
          }
          
          if (header.includes("LinkedIn Connect Sent") && value) {
            const dateValue = new Date(value);
            if (Utilities.formatDate(dateValue, Session.getScriptTimeZone(), 'MM/dd/yyyy') === todayStr) {
              linkedinConnects++;
            }
          }
          
          if (header.includes("LinkedIn DM Sent") && value) {
            const dateValue = new Date(value);
            if (Utilities.formatDate(dateValue, Session.getScriptTimeZone(), 'MM/dd/yyyy') === todayStr) {
              linkedinMessages++;
            }
          }
        }
        
        // Count replies
        const repliedEmail = row[headers.indexOf("Replied to Email?")] === "Yes";
        const repliedLinkedIn = row[headers.indexOf("Replied to LinkedIn?")] === "Yes";
        const replyDate = row[headers.indexOf("Reply Date")];
        
        if ((repliedEmail || repliedLinkedIn) && replyDate) {
          const replyDateValue = new Date(replyDate);
          if (Utilities.formatDate(replyDateValue, Session.getScriptTimeZone(), 'MM/dd/yyyy') === todayStr) {
            repliesReceived++;
          }
        }
      }
      
      const totalSent = emailsSent + linkedinConnects + linkedinMessages;
      const responseRate = totalSent > 0 ? ((repliesReceived / totalSent) * 100).toFixed(1) : 0;
      
      return {
        emailsSent,
        linkedinConnects, 
        linkedinMessages,
        totalOutreach: totalSent,
        repliesReceived,
        responseRate: parseFloat(responseRate)
      };
      
    } catch (error) {
      console.log(`Error getting today's metrics: ${error.toString()}`);
      return {
        emailsSent: 0,
        linkedinConnects: 0,
        linkedinMessages: 0,
        totalOutreach: 0,
        repliesReceived: 0,
        responseRate: 0,
        error: error.toString()
      };
    }
  },
  
  /**
   * Get this week's metrics
   */
  getWeekMetrics: function() {
    // Similar logic to getTodayMetrics but for past 7 days
    return {
      emailsSent: 0,
      linkedinConnects: 0,
      linkedinMessages: 0,
      totalOutreach: 0,
      repliesReceived: 0,
      responseRate: 0
    };
  },
  
  /**
   * Get all-time metrics
   */
  getAllTimeMetrics: function() {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      const data = contactSheet.getDataRange().getValues();
      const headers = data[0];
      
      let totalContacts = data.length - 1;
      let activeContacts = 0;
      let pausedContacts = 0;
      let repliedContacts = 0;
      
      for (let i = 1; i < data.length; i++) {
        const row = data[i];
        const paused = row[headers.indexOf("Paused?")] === "Yes";
        const repliedEmail = row[headers.indexOf("Replied to Email?")] === "Yes";
        const repliedLinkedIn = row[headers.indexOf("Replied to LinkedIn?")] === "Yes";
        
        if (paused) {
          pausedContacts++;
        } else {
          activeContacts++;
        }
        
        if (repliedEmail || repliedLinkedIn) {
          repliedContacts++;
        }
      }
      
      const overallResponseRate = totalContacts > 0 ? ((repliedContacts / totalContacts) * 100).toFixed(1) : 0;
      
      return {
        totalContacts,
        activeContacts,
        pausedContacts,
        repliedContacts,
        overallResponseRate: parseFloat(overallResponseRate)
      };
      
    } catch (error) {
      console.log(`Error getting all-time metrics: ${error.toString()}`);
      return {
        totalContacts: 0,
        activeContacts: 0,
        pausedContacts: 0,
        repliedContacts: 0,
        overallResponseRate: 0,
        error: error.toString()
      };
    }
  },
  
  /**
   * Get campaign status
   */
  getCampaignStatus: function() {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const contactSheet = ss.getSheetByName("ContactList");
      const data = contactSheet.getDataRange().getValues();
      const headers = data[0];
      
      const campaigns = {
        total: data.length - 1,
        running: 0,
        paused: 0,
        completed: 0,
        sequences: {}
      };
      
      for (let i = 1; i < data.length; i++) {
        const row = data[i];
        const paused = row[headers.indexOf("Paused?")] === "Yes";
        const sequence = row[headers.indexOf("Message Sequence Sheet")];
        const repliedEmail = row[headers.indexOf("Replied to Email?")] === "Yes";
        const repliedLinkedIn = row[headers.indexOf("Replied to LinkedIn?")] === "Yes";
        
        // Count by status
        if (repliedEmail || repliedLinkedIn) {
          campaigns.completed++;
        } else if (paused) {
          campaigns.paused++;
        } else {
          campaigns.running++;
        }
        
        // Count by sequence
        if (sequence) {
          if (!campaigns.sequences[sequence]) {
            campaigns.sequences[sequence] = 0;
          }
          campaigns.sequences[sequence]++;
        }
      }
      
      return campaigns;
      
    } catch (error) {
      console.log(`Error getting campaign status: ${error.toString()}`);
      return { error: error.toString() };
    }
  },
  
  /**
   * Get recent errors
   */
  getRecentErrors: function() {
    try {
      const errorLogs = Services.getProperty('error_logs');
      if (!errorLogs) return [];
      
      const errors = JSON.parse(errorLogs);
      return errors.slice(-10); // Return last 10 errors
      
    } catch (error) {
      return [{ error: `Failed to get error logs: ${error.toString()}` }];
    }
  },
  
  /**
   * Get test report from recent test runs
   */
  getTestReport: function() {
    console.log("📋 TEST REPORT");
    console.log("=".repeat(40));
    
    try {
      const testResults = Services.getProperty('last_test_results');
      if (!testResults) {
        console.log("No recent test results found.");
        return { available: false };
      }
      
      const results = JSON.parse(testResults);
      
      console.log(`📅 Test Date: ${results.timestamp}`);
      console.log(`✅ Success: ${results.success ? 'Yes' : 'No'}`);
      console.log(`👥 Contacts Tested: ${results.totalContacts || 0}`);
      console.log(`📧 Emails Sent: ${results.emailsSent || 0}`);
      console.log(`🤝 LinkedIn Connects: ${results.linkedinConnectsSent || 0}`);
      console.log(`💬 LinkedIn Messages: ${results.linkedinMessagesSent || 0}`);
      console.log(`❌ Errors: ${results.errors ? results.errors.length : 0}`);
      
      if (results.errors && results.errors.length > 0) {
        console.log("\nRecent Errors:");
        results.errors.slice(0, 5).forEach(error => {
          console.log(`   • ${error}`);
        });
      }
      
      return results;
      
    } catch (error) {
      console.log(`Error getting test report: ${error.toString()}`);
      return { error: error.toString() };
    }
  }
};

// Top-level wrapper functions for Apps Script dropdown visibility
function getComprehensiveStatus() {
  return Monitor.getComprehensiveStatus();
}

function getSystemHealth() {
  return Monitor.getSystemHealth();
}

function getPerformanceMetrics() {
  return Monitor.getPerformanceMetrics();
}

function getTodayMetrics() {
  return Monitor.getTodayMetrics();
}

function getWeekMetrics() {
  return Monitor.getWeekMetrics();
}

function getAllTimeMetrics() {
  return Monitor.getAllTimeMetrics();
}

function getCampaignStatus() {
  return Monitor.getCampaignStatus();
}

function getRecentErrors() {
  return Monitor.getRecentErrors();
}

function getTestReport() {
  return Monitor.getTestReport();
}

// Legacy function support for backward compatibility
function getAutomationStats() {
  console.log("ℹ️ Legacy function called - redirecting to Monitor.getComprehensiveStatus()");
  return Monitor.getComprehensiveStatus();
}

function showDashboard() {
  console.log("ℹ️ Legacy function called - redirecting to Monitor.getComprehensiveStatus()");
  const status = Monitor.getComprehensiveStatus();
  
  console.log("📊 AUTOMATION DASHBOARD");
  console.log("=".repeat(50));
  console.log(`System Health: ${status.system.healthy ? '✅ Healthy' : '⚠️ Issues'}`);
  console.log(`Emails Today: ${status.performance.today.emailsSent}`);
  console.log(`LinkedIn Connects Today: ${status.performance.today.linkedinConnects}`);
  console.log(`Response Rate: ${status.performance.today.responseRate}%`);
  
  return status;
}