// ======================
// DOGNOSIS OUTREACH AUTOMATION - FACTORIES DOMAIN
// Data structure factories and builders
// ======================

const Factories = {
  /**
   * Create a new contact object with all required fields
   */
  createContact: function(data = {}) {
    return {
      // Core fields
      email: data.email || '',
      firstName: data.firstName || '',
      lastName: data.lastName || '',
      company: data.company || '',
      title: data.title || '',
      linkedinUrl: data.linkedinUrl || '',
      
      // Campaign fields
      sequenceSheet: data.sequenceSheet || 'Default',
      campaignStartDate: data.campaignStartDate || null,
      
      // Status fields
      paused: data.paused || false,
      repliedToEmail: data.repliedToEmail || false,
      repliedToLinkedIn: data.repliedToLinkedIn || false,
      replyDate: data.replyDate || null,
      
      // Metadata
      rowIndex: data.rowIndex || -1,
      createdDate: data.createdDate || new Date(),
      lastModified: data.lastModified || new Date(),
      notes: data.notes || '',
      
      // Computed properties
      fullName: function() {
        return `${this.firstName} ${this.lastName}`.trim();
      },
      
      displayName: function() {
        return this.firstName || this.email || 'Unknown Contact';
      },
      
      isValid: function() {
        return !!(this.email && Services.validateEmail(this.email) && this.sequenceSheet);
      },
      
      isActive: function() {
        return !this.paused && !this.repliedToEmail && !this.repliedToLinkedIn;
      },
      
      hasLinkedIn: function() {
        return !!this.linkedinUrl && Services.validateLinkedInUrl(this.linkedinUrl);
      },
      
      getDaysSinceCampaignStart: function() {
        if (!this.campaignStartDate) return -1;
        const days = Math.floor((new Date() - new Date(this.campaignStartDate)) / (1000 * 60 * 60 * 24));
        return days;
      }
    };
  },
  
  /**
   * Create a sequence configuration object
   */
  createSequenceConfig: function(data = {}) {
    return {
      name: data.name || 'Default',
      description: data.description || '',
      
      // Day arrays
      emailDays: data.emailDays || [],
      linkedinConnectDays: data.linkedinConnectDays || [],
      linkedinMessageDays: data.linkedinMessageDays || [],
      
      // Content map
      dayContent: data.dayContent || {},
      
      // Settings
      maxDays: data.maxDays || 30,
      pauseOnReply: data.pauseOnReply !== false,
      
      // Methods
      getDayContent: function(day) {
        return this.dayContent[day] || null;
      },
      
      getAllDays: function() {
        const allDays = [
          ...this.emailDays,
          ...this.linkedinConnectDays,
          ...this.linkedinMessageDays
        ];
        return [...new Set(allDays)].sort((a, b) => a - b);
      },
      
      hasDay: function(day) {
        return this.getAllDays().includes(day);
      },
      
      getNextActionDay: function(currentDay) {
        const allDays = this.getAllDays();
        return allDays.find(d => d > currentDay) || null;
      },
      
      isValid: function() {
        return this.name && this.getAllDays().length > 0;
      }
    };
  },
  
  /**
   * Create a campaign object
   */
  createCampaign: function(data = {}) {
    return {
      id: data.id || this.generateId('campaign'),
      name: data.name || 'New Campaign',
      
      // Configuration
      sequence: data.sequence || 'Default',
      startDate: data.startDate || new Date(),
      endDate: data.endDate || null,
      
      // Limits
      dailyEmailLimit: data.dailyEmailLimit || 50,
      dailyLinkedInLimit: data.dailyLinkedInLimit || 25,
      
      // Status
      status: data.status || 'active', // active, paused, completed
      
      // Metrics
      metrics: {
        totalContacts: data.totalContacts || 0,
        emailsSent: data.emailsSent || 0,
        linkedinConnectsSent: data.linkedinConnectsSent || 0,
        linkedinMessagesSent: data.linkedinMessagesSent || 0,
        replies: data.replies || 0,
        responseRate: data.responseRate || 0
      },
      
      // Methods
      isActive: function() {
        return this.status === 'active';
      },
      
      updateMetrics: function(newMetrics) {
        Object.assign(this.metrics, newMetrics);
        if (this.metrics.totalContacts > 0) {
          this.metrics.responseRate = (this.metrics.replies / this.metrics.totalContacts * 100).toFixed(1);
        }
      }
    };
  },
  
  /**
   * Create an automation task
   */
  createTask: function(data = {}) {
    return {
      id: data.id || this.generateId('task'),
      type: data.type || 'email', // email, linkedinConnect, linkedinMessage
      
      // Target
      contact: data.contact || null,
      day: data.day || 1,
      
      // Content
      content: data.content || {},
      
      // Scheduling
      scheduledFor: data.scheduledFor || new Date(),
      priority: data.priority || 50,
      
      // Status
      status: data.status || 'pending', // pending, processing, completed, failed
      attempts: data.attempts || 0,
      maxAttempts: data.maxAttempts || 3,
      
      // Results
      completedAt: data.completedAt || null,
      error: data.error || null,
      
      // Methods
      canRetry: function() {
        return this.status === 'failed' && this.attempts < this.maxAttempts;
      },
      
      incrementAttempts: function() {
        this.attempts++;
        if (this.attempts >= this.maxAttempts) {
          this.status = 'failed';
        }
      },
      
      complete: function() {
        this.status = 'completed';
        this.completedAt = new Date();
      },
      
      fail: function(error) {
        this.status = 'failed';
        this.error = error;
        this.incrementAttempts();
      }
    };
  },
  
  /**
   * Create a batch processing job
   */
  createBatch: function(data = {}) {
    return {
      id: data.id || this.generateId('batch'),
      type: data.type || 'mixed',
      
      // Tasks
      tasks: data.tasks || [],
      
      // Configuration
      maxSize: data.maxSize || 50,
      parallel: data.parallel || false,
      
      // Status
      status: data.status || 'pending',
      startedAt: data.startedAt || null,
      completedAt: data.completedAt || null,
      
      // Results
      results: {
        total: data.tasks ? data.tasks.length : 0,
        completed: 0,
        failed: 0,
        errors: []
      },
      
      // Methods
      addTask: function(task) {
        if (this.tasks.length < this.maxSize) {
          this.tasks.push(task);
          this.results.total++;
          return true;
        }
        return false;
      },
      
      start: function() {
        this.status = 'processing';
        this.startedAt = new Date();
      },
      
      complete: function() {
        this.status = 'completed';
        this.completedAt = new Date();
      },
      
      recordSuccess: function() {
        this.results.completed++;
      },
      
      recordFailure: function(error) {
        this.results.failed++;
        this.results.errors.push(error);
      },
      
      getSuccessRate: function() {
        if (this.results.total === 0) return 0;
        return (this.results.completed / this.results.total * 100).toFixed(1);
      }
    };
  },
  
  /**
   * Create an error log entry
   */
  createErrorLog: function(data = {}) {
    return {
      id: data.id || this.generateId('error'),
      timestamp: data.timestamp || new Date(),
      
      // Error details
      function: data.function || 'Unknown',
      error: data.error || 'Unknown error',
      stack: data.stack || null,
      
      // Context
      context: data.context || {},
      
      // Classification
      severity: data.severity || 'error', // info, warning, error, critical
      category: data.category || 'general', // general, api, data, system
      
      // Resolution
      resolved: data.resolved || false,
      resolution: data.resolution || null,
      
      // Methods
      resolve: function(resolution) {
        this.resolved = true;
        this.resolution = resolution;
      },
      
      getSummary: function() {
        return `[${this.severity.toUpperCase()}] ${this.function}: ${this.error}`;
      }
    };
  },
  
  /**
   * Create a performance metric
   */
  createMetric: function(data = {}) {
    return {
      id: data.id || this.generateId('metric'),
      name: data.name || 'Unnamed Metric',
      
      // Measurement
      value: data.value || 0,
      unit: data.unit || 'count',
      timestamp: data.timestamp || new Date(),
      
      // Aggregation
      type: data.type || 'gauge', // gauge, counter, histogram
      tags: data.tags || {},
      
      // Methods
      increment: function(amount = 1) {
        if (this.type === 'counter') {
          this.value += amount;
        }
      },
      
      set: function(value) {
        this.value = value;
        this.timestamp = new Date();
      },
      
      addTag: function(key, value) {
        this.tags[key] = value;
      }
    };
  },
  
  /**
   * Create a system event
   */
  createEvent: function(data = {}) {
    return {
      id: data.id || this.generateId('event'),
      type: data.type || 'info',
      
      // Event details
      title: data.title || 'System Event',
      description: data.description || '',
      timestamp: data.timestamp || new Date(),
      
      // Source
      source: data.source || 'System',
      user: data.user || Session.getActiveUser().getEmail(),
      
      // Data
      data: data.data || {},
      
      // Methods
      toLogString: function() {
        return `[${this.timestamp.toISOString()}] ${this.type.toUpperCase()}: ${this.title} (${this.source})`;
      }
    };
  },
  
  /**
   * Create a notification
   */
  createNotification: function(data = {}) {
    return {
      id: data.id || this.generateId('notification'),
      
      // Content
      title: data.title || 'Notification',
      message: data.message || '',
      type: data.type || 'info', // info, success, warning, error
      
      // Delivery
      channel: data.channel || 'email', // email, ui, webhook
      recipient: data.recipient || Session.getActiveUser().getEmail(),
      
      // Status
      sent: data.sent || false,
      sentAt: data.sentAt || null,
      read: data.read || false,
      readAt: data.readAt || null,
      
      // Methods
      markAsSent: function() {
        this.sent = true;
        this.sentAt = new Date();
      },
      
      markAsRead: function() {
        this.read = true;
        this.readAt = new Date();
      }
    };
  },
  
  /**
   * Generate unique ID for objects
   */
  generateId: function(prefix = 'obj') {
    const timestamp = Date.now().toString(36);
    const random = Math.random().toString(36).substr(2, 5);
    return `${prefix}_${timestamp}_${random}`;
  },
  
  /**
   * Create objects from spreadsheet row
   */
  createFromRow: function(type, row, headers, rowIndex) {
    switch (type) {
      case 'contact':
        return this.createContactFromRow(row, headers, rowIndex);
      
      case 'sequence':
        return this.createSequenceFromRow(row, headers, rowIndex);
        
      default:
        throw new Error(`Unknown type: ${type}`);
    }
  },
  
  /**
   * Create contact from spreadsheet row
   */
  createContactFromRow: function(row, headers, rowIndex) {
    const getColValue = (colName) => {
      const index = headers.indexOf(colName);
      return index !== -1 ? row[index] : null;
    };
    
    return this.createContact({
      email: getColValue(COLUMN_NAMES.EMAIL),
      firstName: getColValue(COLUMN_NAMES.FIRST_NAME),
      lastName: getColValue(COLUMN_NAMES.LAST_NAME),
      company: getColValue(COLUMN_NAMES.COMPANY),
      title: getColValue(COLUMN_NAMES.TITLE),
      linkedinUrl: getColValue(COLUMN_NAMES.LINKEDIN_URL),
      sequenceSheet: getColValue(COLUMN_NAMES.MESSAGE_SEQUENCE_SHEET),
      campaignStartDate: getColValue(COLUMN_NAMES.CAMPAIGN_START_DATE),
      paused: getColValue(COLUMN_NAMES.PAUSED) === 'Yes',
      repliedToEmail: getColValue(COLUMN_NAMES.REPLIED_TO_EMAIL) === 'Yes',
      repliedToLinkedIn: getColValue(COLUMN_NAMES.REPLIED_TO_LINKEDIN) === 'Yes',
      replyDate: getColValue(COLUMN_NAMES.REPLY_DATE),
      rowIndex: rowIndex
    });
  },
  
  /**
   * Create sequence from spreadsheet data
   */
  createSequenceFromRow: function(row, headers, rowIndex) {
    const getColValue = (colName) => {
      const index = headers.indexOf(colName);
      return index !== -1 ? row[index] : null;
    };
    
    const day = parseInt(getColValue(SEQUENCE_COLUMNS.DAY) || 0);
    const step = getColValue(SEQUENCE_COLUMNS.STEP);
    
    return {
      day: day,
      step: step,
      subject: getColValue(SEQUENCE_COLUMNS.SUBJECT),
      body: getColValue(SEQUENCE_COLUMNS.BODY),
      emailType: getColValue(SEQUENCE_COLUMNS.EMAIL_TYPE),
      rowIndex: rowIndex
    };
  }
};

// Legacy function mappings
function createContactObject(data) {
  return Factories.createContact(data);
}

function createTaskObject(type, contact, day) {
  return Factories.createTask({
    type: type,
    contact: contact,
    day: day
  });
}

function createBatchObject(type, tasks) {
  return Factories.createBatch({
    type: type,
    tasks: tasks
  });
}