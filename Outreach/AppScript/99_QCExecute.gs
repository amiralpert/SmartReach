/*
==============================================
DOGNOSIS OUTREACH AUTOMATION - QC & TESTING
==============================================
Main system testing functions (cleaned up codebase - Jan 2025)

Key Functions:
- runFullQCTest() - Comprehensive system validation
- testLinkedInSystem() - PhantomBuster integration test
- testEmailSystem() - Gmail integration test
- testSystemInitialization() - Core setup test
*/

/**
 * MAIN QC EXECUTION FUNCTION
 * This will appear in Apps Script dropdown menu
 */
function runFullQCTest() {
  console.log('🚀 Starting Comprehensive QC Testing...');
  
  try {
    // Clear previous results
    PropertiesService.getScriptProperties().deleteProperty('QC_RESULTS');
    PropertiesService.getScriptProperties().deleteProperty('QC_FINAL_SUMMARY');
    PropertiesService.getScriptProperties().deleteProperty('QC_EXECUTION_COMPLETED');
    PropertiesService.getScriptProperties().deleteProperty('QC_COMPLETION_TIME');
    PropertiesService.getScriptProperties().deleteProperty('QC_EXECUTION_ERROR');
    
    // Initialize QC session
    const startTime = new Date().toISOString();
    console.log(`📊 QC Session Started: ${startTime}`);
    
    // Execute Stage 1: Component Testing
    console.log('\n🔧 STAGE 1: Component Testing');
    const stage1Results = executeStage1Testing();
    
    // Execute Stage 2: Integration Testing  
    console.log('\n🔗 STAGE 2: Integration Testing');
    const stage2Results = executeStage2Testing();
    
    // Execute Stage 3: Live Simulation
    console.log('\n⚡ STAGE 3: Live Simulation (30min compressed)');
    const stage3Results = executeStage3Testing();
    
    // Execute Stage 4: Production Assessment
    console.log('\n📋 STAGE 4: Production Assessment');
    const stage4Results = executeStage4Testing();
    
    // Generate final summary
    const finalSummary = generateQCSummary([stage1Results, stage2Results, stage3Results, stage4Results]);
    
    // Store results
    PropertiesService.getScriptProperties().setProperty('QC_FINAL_SUMMARY', JSON.stringify(finalSummary));
    PropertiesService.getScriptProperties().setProperty('QC_EXECUTION_COMPLETED', 'true');
    PropertiesService.getScriptProperties().setProperty('QC_COMPLETION_TIME', new Date().toISOString());
    
    console.log('\n✅ QC Testing Complete!');
    console.log('📊 Results stored in PropertiesService');
    
    // Output results in simple format for copying
    console.log('\n📋 QC RESULTS SUMMARY (Copy for Claude):');
    console.log('='.repeat(60));
    console.log(`Execution Time: ${finalSummary.executionTime}`);
    console.log(`Total Tests: ${finalSummary.totalTests}`);
    console.log(`Passed: ${finalSummary.testsByStatus.PASSED} | Failed: ${finalSummary.testsByStatus.FAILED} | Blocked: ${finalSummary.testsByStatus.BLOCKED}`);
    console.log(`Pass Rate: ${finalSummary.systemReadiness.passRate}%`);
    console.log(`System Status: ${finalSummary.systemReadiness.status}`);
    console.log(`Critical Issues: ${finalSummary.criticalIssues.length}`);
    console.log('='.repeat(60));
    
    return finalSummary;
    
  } catch (error) {
    console.error('❌ QC Testing Failed:', error);
    PropertiesService.getScriptProperties().setProperty('QC_EXECUTION_ERROR', error.toString());
    PropertiesService.getScriptProperties().setProperty('QC_COMPLETION_TIME', new Date().toISOString());
    throw error;
  }
}

/**
 * Stage 1: Component Testing
 */
function executeStage1Testing() {
  console.log('Testing individual components...');
  
  const results = [];
  
  // Test 1: System Initialization
  results.push(testSystemInitialization());
  
  // Test 2: Data Management
  results.push(testDataManagement());
  
  // Test 3: Email System
  results.push(testEmailSystem());
  
  // Test 4: LinkedIn System
  results.push(testLinkedInSystem());
  
  // Test 5: Campaign Engine
  results.push(testCampaignEngine());
  
  // Test 6: Reply Detection
  results.push(testReplyDetection());
  
  // Test 7: Monitoring
  results.push(testMonitoring());
  
  // Test 8: Error Handling
  results.push(testErrorHandling());
  
  return {
    stage: 'STAGE_1_COMPONENTS',
    tests: results,
    totalTests: results.length,
    passedTests: results.filter(r => r.status === 'PASSED').length,
    failedTests: results.filter(r => r.status === 'FAILED').length,
    blockedTests: results.filter(r => r.status === 'BLOCKED').length
  };
}

/**
 * Stage 2: Integration Testing
 */
function executeStage2Testing() {
  console.log('Testing system integration...');
  
  const results = [];
  
  results.push(testFullDataFlow());
  results.push(testMultiContactExecution());
  results.push(testFailureRecovery());
  
  return {
    stage: 'STAGE_2_INTEGRATION', 
    tests: results,
    totalTests: results.length,
    passedTests: results.filter(r => r.status === 'PASSED').length,
    failedTests: results.filter(r => r.status === 'FAILED').length,
    blockedTests: results.filter(r => r.status === 'BLOCKED').length
  };
}

/**
 * Stage 3: Live Simulation (30-minute compressed)
 */
function executeStage3Testing() {
  console.log('Executing accelerated live simulation...');
  
  const results = [];
  
  results.push(testLiveSimulationSetup());
  results.push(testAcceleratedSequence());
  results.push(testReplyHandlingLive());
  results.push(testCampaignCompletion());
  
  return {
    stage: 'STAGE_3_LIVE_SIMULATION',
    tests: results, 
    totalTests: results.length,
    passedTests: results.filter(r => r.status === 'PASSED').length,
    failedTests: results.filter(r => r.status === 'FAILED').length,
    blockedTests: results.filter(r => r.status === 'BLOCKED').length
  };
}

/**
 * Stage 4: Production Assessment
 */
function executeStage4Testing() {
  console.log('Assessing production readiness...');
  
  const results = [];
  
  results.push(testProductionReadiness());
  results.push(testScalingCapability());
  results.push(generateGoNoGoDecision());
  
  return {
    stage: 'STAGE_4_ASSESSMENT',
    tests: results,
    totalTests: results.length, 
    passedTests: results.filter(r => r.status === 'PASSED').length,
    failedTests: results.filter(r => r.status === 'FAILED').length,
    blockedTests: results.filter(r => r.status === 'BLOCKED').length
  };
}

// Individual test functions
function testSystemInitialization() {
  console.log('🔧 Testing system initialization...');
  
  try {
    // Test would check if 01_Setup.js functions exist and work
    // For now, returning manual validation requirement
    
    return {
      testId: 'SYS_INIT_001',
      description: 'System Initialization & Setup',
      status: 'BLOCKED',
      issues: ['Requires manual validation of 01_Setup.js:runInitialSetup()'],
      resolution: 'Execute setup manually and validate Google Sheets creation',
      duration: 45,
      priority: 'HIGH'
    };
    
  } catch (error) {
    return {
      testId: 'SYS_INIT_001', 
      description: 'System Initialization & Setup',
      status: 'FAILED',
      issues: [error.toString()],
      resolution: 'Fix initialization errors',
      duration: 0,
      priority: 'CRITICAL'
    };
  }
}

function testDataManagement() {
  console.log('📊 Testing data management...');
  
  return {
    testId: 'DATA_MGT_001',
    description: 'Data Management & Import System', 
    status: 'BLOCKED',
    issues: ['Requires manual testing of CSV import and field mapping'],
    resolution: 'Import test data and validate processing',
    duration: 60,
    priority: 'HIGH'
  };
}

function testEmailSystem() {
  console.log('📧 Testing email system...');
  
  return {
    testId: 'EMAIL_SYS_001',
    description: 'Email System Comprehensive Testing',
    status: 'BLOCKED', 
    issues: ['Requires Gmail API authentication and template validation'],
    resolution: 'Test email sending with dummy accounts',
    duration: 90,
    priority: 'CRITICAL'
  };
}

function testLinkedInSystem() {
  console.log('🔗 Testing LinkedIn system...');
  
  return {
    testId: 'LNKD_SYS_001',
    description: 'LinkedIn Automation System',
    status: 'BLOCKED',
    issues: ['Requires PhantomBuster agent testing'],
    resolution: 'Test connection requests with dummy profiles', 
    duration: 120,
    priority: 'HIGH'
  };
}

function testCampaignEngine() {
  console.log('⚙️ Testing campaign engine...');
  
  return {
    testId: 'CAMP_ENG_001',
    description: 'Campaign Orchestration Engine',
    status: 'BLOCKED',
    issues: ['Requires sequence testing with multiple contacts'],
    resolution: 'Execute multi-contact campaign test',
    duration: 75,
    priority: 'CRITICAL'
  };
}

function testReplyDetection() {
  console.log('↩️ Testing reply detection...');
  
  return {
    testId: 'REPLY_DET_001',
    description: 'Reply Detection & Campaign Management', 
    status: 'BLOCKED',
    issues: ['Requires live reply testing from dummy accounts'],
    resolution: 'Generate test replies and validate detection',
    duration: 60,
    priority: 'CRITICAL'
  };
}

function testMonitoring() {
  console.log('📊 Testing monitoring system...');
  
  return {
    testId: 'MONITOR_001',
    description: 'Monitoring & Analytics System',
    status: 'BLOCKED',
    issues: ['Requires validation of metrics calculation'],
    resolution: 'Review monitoring dashboards and reports',
    duration: 45,
    priority: 'MEDIUM'
  };
}

function testErrorHandling() {
  console.log('🛠️ Testing error handling...');
  
  return {
    testId: 'ERROR_HDL_001',
    description: 'Error Handling & Recovery Systems',
    status: 'BLOCKED', 
    issues: ['Requires failure simulation testing'],
    resolution: 'Simulate API failures and validate recovery',
    duration: 30,
    priority: 'HIGH'
  };
}

function testFullDataFlow() {
  console.log('🌊 Testing full data flow...');
  
  return {
    testId: 'INTEG_001',
    description: 'Full Data Flow Validation',
    status: 'BLOCKED',
    issues: ['Requires end-to-end workflow execution'],
    resolution: 'Execute complete contact import to campaign completion',
    duration: 120,
    priority: 'CRITICAL'
  };
}

function testMultiContactExecution() {
  console.log('👥 Testing multi-contact execution...');
  
  return {
    testId: 'INTEG_002', 
    description: 'Multi-Contact Campaign Execution',
    status: 'BLOCKED',
    issues: ['Requires batch processing validation'],
    resolution: 'Test 50+ contacts simultaneously',
    duration: 180,
    priority: 'CRITICAL'
  };
}

function testFailureRecovery() {
  console.log('🔄 Testing failure recovery...');
  
  return {
    testId: 'INTEG_003',
    description: 'Failure Recovery Validation',
    status: 'BLOCKED',
    issues: ['Requires controlled failure simulation'], 
    resolution: 'Simulate various failure conditions',
    duration: 90,
    priority: 'HIGH'
  };
}

function testLiveSimulationSetup() {
  console.log('⚡ Testing live simulation setup...');
  
  return {
    testId: 'LIVE_001',
    description: 'Live Simulation Setup',
    status: 'BLOCKED',
    issues: ['Requires 10 dummy accounts preparation'],
    resolution: 'Prepare dummy Gmail and LinkedIn accounts',
    duration: 5,
    priority: 'CRITICAL'
  };
}

function testAcceleratedSequence() {
  console.log('🚀 Testing accelerated sequence...');
  
  return {
    testId: 'LIVE_002',
    description: 'Accelerated 30-Minute Sequence',
    status: 'BLOCKED', 
    issues: ['Requires live email and LinkedIn execution'],
    resolution: 'Execute compressed 27-day sequence in 30 minutes',
    duration: 30,
    priority: 'CRITICAL'
  };
}

function testReplyHandlingLive() {
  console.log('↩️ Testing live reply handling...');
  
  return {
    testId: 'LIVE_003',
    description: 'Live Reply Detection Testing',
    status: 'BLOCKED',
    issues: ['Requires real replies from dummy accounts'],
    resolution: 'Generate replies and validate immediate detection',
    duration: 10,
    priority: 'CRITICAL'
  };
}

function testCampaignCompletion() {
  console.log('🏁 Testing campaign completion...');
  
  return {
    testId: 'LIVE_004',
    description: 'Campaign Completion Validation',
    status: 'BLOCKED',
    issues: ['Requires full lifecycle completion'],
    resolution: 'Validate proper campaign completion and status updates', 
    duration: 5,
    priority: 'HIGH'
  };
}

function testProductionReadiness() {
  console.log('🎯 Testing production readiness...');
  
  return {
    testId: 'PROD_001',
    description: 'Production Readiness Assessment',
    status: 'BLOCKED',
    issues: ['Requires comprehensive system review'],
    resolution: 'Review all test results and system capabilities',
    duration: 60,
    priority: 'CRITICAL'
  };
}

function testScalingCapability() {
  console.log('📈 Testing scaling capability...');
  
  return {
    testId: 'PROD_002', 
    description: 'System Scaling Assessment',
    status: 'BLOCKED',
    issues: ['Requires load and capacity analysis'],
    resolution: 'Determine optimal batch sizes and processing limits',
    duration: 30,
    priority: 'HIGH'
  };
}

function generateGoNoGoDecision() {
  console.log('⚖️ Generating Go/No-Go decision...');
  
  return {
    testId: 'PROD_003',
    description: 'Go/No-Go Decision',
    status: 'BLOCKED',
    issues: ['Requires final assessment based on all test results'],
    resolution: 'Make production deployment recommendation',
    duration: 30, 
    priority: 'CRITICAL'
  };
}

function generateQCSummary(stageResults) {
  const allTests = stageResults.flatMap(stage => stage.tests);
  const totalTests = allTests.length;
  const passedTests = allTests.filter(t => t.status === 'PASSED').length; 
  const failedTests = allTests.filter(t => t.status === 'FAILED').length;
  const blockedTests = allTests.filter(t => t.status === 'BLOCKED').length;
  
  const passRate = totalTests > 0 ? Math.round((passedTests / totalTests) * 100) : 0;
  const criticalIssues = allTests.filter(t => t.priority === 'CRITICAL' && t.status !== 'PASSED');
  
  let systemReadiness = 'NOT_READY';
  let readinessMessage = 'System requires manual testing completion';
  let confidence = 'LOW';
  
  if (failedTests === 0 && blockedTests === 0) {
    systemReadiness = 'READY';
    readinessMessage = 'All tests passed - system ready for production';
    confidence = 'HIGH';
  } else if (criticalIssues.length === 0 && failedTests === 0) {
    systemReadiness = 'CONDITIONAL';
    readinessMessage = 'System conditionally ready - complete remaining tests';
    confidence = 'MEDIUM';
  }
  
  return {
    executionTime: new Date().toISOString(),
    totalTests: totalTests,
    testsByStatus: {
      PASSED: passedTests,
      FAILED: failedTests, 
      BLOCKED: blockedTests
    },
    testsByStage: stageResults.map(stage => ({
      stage: stage.stage,
      passed: stage.passedTests,
      failed: stage.failedTests,
      blocked: stage.blockedTests,
      total: stage.totalTests
    })),
    systemReadiness: {
      status: systemReadiness,
      message: readinessMessage,
      confidence: confidence,
      passRate: passRate
    },
    criticalIssues: criticalIssues.map(issue => ({
      testId: issue.testId,
      description: issue.description,
      issues: issue.issues,
      priority: issue.priority
    })),
    recommendations: generateRecommendations(allTests),
    detailedResults: allTests
  };
}

function generateRecommendations(allTests) {
  const recommendations = [];
  
  const criticalFailed = allTests.filter(t => t.priority === 'CRITICAL' && t.status === 'FAILED');
  const blockedTests = allTests.filter(t => t.status === 'BLOCKED');
  
  if (criticalFailed.length > 0) {
    recommendations.push('IMMEDIATE: Resolve all critical failures before proceeding');
  }
  
  if (blockedTests.length > 0) {
    recommendations.push('HIGH: Complete manual testing for all blocked tests');
  }
  
  recommendations.push('Execute 30-minute live simulation with 10 dummy accounts');
  recommendations.push('Validate reply detection accuracy at 100%');
  recommendations.push('Confirm multi-channel coordination works flawlessly');
  
  return recommendations;
}

/**
 * MONITORING FUNCTIONS - These will also appear in dropdown
 */

function checkQCStatus() {
  const completed = PropertiesService.getScriptProperties().getProperty('QC_EXECUTION_COMPLETED');
  const completionTime = PropertiesService.getScriptProperties().getProperty('QC_COMPLETION_TIME');
  const hasError = PropertiesService.getScriptProperties().getProperty('QC_EXECUTION_ERROR');
  
  console.log('📊 QC EXECUTION STATUS:');
  console.log(`Completed: ${completed === 'true' ? '✅ YES' : '❌ NO'}`);
  console.log(`Completion Time: ${completionTime || 'Not completed'}`);
  console.log(`Has Errors: ${hasError ? '⚠️ YES - ' + hasError : '✅ NO'}`);
  
  return {
    completed: completed === 'true',
    completionTime: completionTime,
    hasError: hasError !== null,
    error: hasError
  };
}

function getQCResults() {
  const summaryJson = PropertiesService.getScriptProperties().getProperty('QC_FINAL_SUMMARY');
  
  if (!summaryJson) {
    console.log('❌ No QC results found');
    return null;
  }
  
  try {
    const summary = JSON.parse(summaryJson);
    
    console.log('📊 QC RESULTS SUMMARY:');
    console.log(`Total Tests: ${summary.totalTests}`);
    console.log(`Pass Rate: ${summary.systemReadiness.passRate}%`);
    console.log(`System Status: ${summary.systemReadiness.status}`);
    console.log(`Critical Issues: ${summary.criticalIssues.length}`);
    
    return summary;
    
  } catch (error) {
    console.log('❌ Failed to parse QC results:', error);
    return null;
  }
}

function clearQCResults() {
  PropertiesService.getScriptProperties().deleteProperty('QC_RESULTS');
  PropertiesService.getScriptProperties().deleteProperty('QC_FINAL_SUMMARY');
  PropertiesService.getScriptProperties().deleteProperty('QC_EXECUTION_COMPLETED');
  PropertiesService.getScriptProperties().deleteProperty('QC_COMPLETION_TIME');
  PropertiesService.getScriptProperties().deleteProperty('QC_EXECUTION_ERROR');
  
  console.log('🧹 QC results cleared');
  return 'All QC results and flags have been cleared';
}

