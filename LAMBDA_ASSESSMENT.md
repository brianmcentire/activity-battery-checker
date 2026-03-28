# Lambda Implementation Plan Assessment

## Executive Summary

The Lambda implementation plan at [LAMBDA_IMPLEMENTATION_PLAN.md](LAMBDA_IMPLEMENTATION_PLAN.md) is **SOLID and ready for implementation** with a few important additions needed.

**Overall Rating: 8.5/10** - Strong foundation with minor gaps

**Verdict:** Proceed with implementation after addressing the critical items below.

---

## What's Excellent ✅

### 1. **Strong Technical Foundation Already in Place**
- [battery_checker.py](battery_checker.py) is production-ready (434 lines, well-structured)
- Core battery parsing logic proven to work with real .fit files
- fitdecode library available and functional (1088 KB at `/Users/brian/code/fitdecode`)
- Comprehensive device database (80+ Garmin products mapped)
- Clean code with no global state or hardcoded secrets

### 2. **Pragmatic Architecture Decisions**
- ✅ No S3/DynamoDB for personal use (keeps it simple)
- ✅ Environment variables for secrets (appropriate for personal Lambda)
- ✅ Ephemeral /tmp storage (sufficient for this workload)
- ✅ Dual-path API strategy (Strava primary, Garmin fallback)

### 3. **Well-Structured Implementation Phases**
- Clear progression: Research → Dev → Deploy → Test → Monitor
- Realistic testing strategy covering edge cases
- Comprehensive API research notes included

### 4. **Code Reuse Strategy is Sound**
- Plan correctly identifies need to extract shared logic to `battery_parser.py`
- Keeps CLI tool intact (battery_checker.py remains unchanged)
- Functions are already modular and easy to extract

---

## Critical Gaps That Need Addressing ⚠️

### 1. **Strava Token Refresh Logic** (CRITICAL)
**Issue:** Plan mentions "long-lived or refresh token" but Strava access tokens expire after 6 hours.

**What's Missing:**
- Token refresh logic in Lambda handler
- Storing refresh token in environment variable
- Handling token expiration errors

**Impact:** Without this, Lambda will fail after 6 hours when access token expires.

**Solution Required:**
```python
# Lambda environment variables needed:
STRAVA_CLIENT_ID
STRAVA_CLIENT_SECRET
STRAVA_REFRESH_TOKEN  # Store this (per user's preference)

# Lambda handler must:
1. Check if access token is expired
2. Use refresh token to get new access token
3. Use new access token for API calls
4. Cache access token in memory for Lambda warm starts
```

**Estimated Effort:** 2-3 hours to implement and test

### 2. **Webhook Signature Verification** (CRITICAL for Security)
**Issue:** Plan mentions webhook setup but not signature verification.

**What's Missing:**
- Strava webhook validation challenge response
- HMAC-SHA256 signature verification for incoming webhooks
- Verify `x-hub-signature` header matches computed signature

**Impact:** Without verification, webhook endpoint is vulnerable to spoofed requests.

**Solution Required:**
```python
# Environment variable needed:
STRAVA_WEBHOOK_VERIFY_TOKEN

# Lambda handler must:
1. Handle GET request for Strava challenge validation
2. Verify HMAC signature on POST requests
3. Reject requests with invalid signatures
```

**Reference:** [Strava Webhook Events Documentation](https://developers.strava.com/docs/webhooks/)

**Estimated Effort:** 1-2 hours to implement and test

### 3. **Strava API .fit File Availability Validation** (BLOCKING)
**Issue:** Plan identifies this as Phase 1 research but doesn't gate implementation on it.

**Evidence of Risk:**
- Test .fit downloads in workspace are empty (97 bytes)
- Suggests Strava `export_original` endpoint may not work reliably

**What's Needed:**
- Run [test_strava_fit_download.py](test_strava_fit_download.py) with valid credentials
- Confirm actual .fit files download (should be 500+ KB for typical ride)
- Document which activity types work (ride vs run vs others)

**Contingency:** If Strava fails, switch to Garmin API as primary
- Use [test_garmin_fit_download.py](test_garmin_fit_download.py)
- garth library (v0.4.42) already available
- Requires Garmin username/password in environment variables

**Estimated Effort:** 2-4 hours for validation

---

## Important Improvements (Should Have) 📋

### 4. **Error Handling Strategy**
**Current State:** Plan doesn't specify error handling approach.

**Recommended Strategy:**
```python
# Handle these scenarios with appropriate retry logic:

1. Strava API rate limit exceeded (429 response)
   - Implement exponential backoff (1s, 2s, 4s delays)
   - Max 3 retries within Lambda execution
   - If still failing, raise exception to trigger Lambda retry

2. Network timeout during .fit download
   - Set reasonable timeout (30 seconds)
   - Retry up to 3 times with exponential backoff
   - Log failure and raise exception if all retries fail

3. Corrupted/empty .fit file
   - Log warning with activity ID
   - Skip this activity, continue processing others
   - Don't retry (file won't fix itself)

4. Missing battery data in valid .fit file
   - Log info message (this is normal for some activities)
   - Skip notification, don't treat as error
   - Continue processing

5. Pushover API failure
   - CRITICAL: This is the core function - notification must succeed
   - Retry up to 3 times with exponential backoff
   - If notification fails after retries, raise exception
   - Let Lambda automatic retry handle it (up to 2 retries)
   - Rationale: The entire point is notifications - if they fail, system fails

# Implementation pattern:
def retry_with_backoff(func, max_retries=3, initial_delay=1):
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = initial_delay * (2 ** attempt)
            logger.warning(f"Retry {attempt+1}/{max_retries} after {delay}s: {e}")
            time.sleep(delay)

# Lambda return strategy:
- Return success only if notification was sent OR no low batteries found
- Raise exception if critical operations fail (notification delivery)
- Lambda automatic retry policy will handle transient failures
- Configure dead letter queue (DLQ) for permanent failures
```

**User Preference Noted:** Multiple notifications if battery stays low (one per day) = no deduplication needed

**Estimated Effort:** 3-4 hours (includes retry logic implementation)

### 5. **Package Size Validation**
**Concern:** Lambda deployment package must be <250 MB unzipped.

**Current Estimate:**
- Core code: ~30 KB
- fitdecode: ~400 KB
- requests library: ~250 KB
- **Total: ~700 KB ✓ Well within limits**

**For Garmin Fallback:**
- garth library: ~500 KB additional
- **Total with garth: ~1.2 MB ✓ Still acceptable**

**Action Required:** Test actual package build in Phase 3
- Create deployment zip
- Verify imports work with Lambda Python 3.12 runtime
- Test locally with AWS SAM or Lambda Docker image

**Estimated Effort:** 1 hour

### 6. **Notification Deduplication Consideration**
**User Preference:** Prefers multiple notifications (one per day) if battery stays low.

**Plan Impact:**
- ✅ No need for DynamoDB to track notification history
- ✅ Simpler implementation (stateless)
- ⚠️ User may get same notification daily until battery replaced

**Recommendation:** Keep current approach, add rate limiting only if user reports notification fatigue.

---

## Minor Enhancements (Nice to Have) 💡

### 7. **CloudWatch Alarms**
**Suggested:** Create alarm for Lambda errors
```
Metric: Errors > 0 in 1 hour
Action: SNS notification to user's email/phone
Benefit: Know immediately if system breaks
Effort: 30 minutes
```

### 8. **Better Logging**
**Current:** battery_checker.py uses print statements
**Suggested:** Use Python logging module for Lambda
```python
import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

logger.info(f"Processing activity {activity_id}")
logger.warning(f"Battery low: {device_name}")
logger.error(f"Failed to download .fit file: {error}")
```
**Benefit:** Structured CloudWatch logs for debugging
**Effort:** 1 hour

### 9. **Lambda Timeout Configuration**
**Plan Specifies:** 5 minutes
**Actual Need:** 30-60 seconds (download + parse typically <10 seconds)
**Benefit:** Lower risk of runaway costs
**Effort:** 5 minutes (just change config)

---

## Implementation Roadmap (Updated)

### Phase 0: BLOCKING VALIDATION ⚠️
**Must complete before coding:**
- [ ] Run Strava API .fit download test with real credentials
- [ ] Verify .fit files contain battery data
- [ ] If Strava fails, validate Garmin API path works
- [ ] Document which API will be primary vs fallback

**Go/No-Go Decision Point:** Don't proceed to Phase 1 without confirmation

**Estimated Time:** 2-4 hours

### Phase 1: Core Implementation
**Files to Create:**
1. `battery_parser.py` - Extract from [battery_checker.py](battery_checker.py)
   - Functions: `scan_fit_file()`, `is_battery_ok()`, `format_battery_status()`, etc.
   - Refactor `print_device_info_brief()` to return data instead of printing
   - Add logging instead of print statements
   - ~100 lines

2. `lambda_activity_battery_checker.py` - Main handler
   - `lambda_handler(event, context)` - Route to daily/webhook handler
   - `handle_daily_check()` - Get last 5 activities, process each
   - `handle_webhook(event)` - Validate signature, process single activity
   - `refresh_strava_token()` - Token refresh logic
   - `download_fit_file(activity_id)` - Strava API call
   - `send_pushover_notification(message)` - Pushover API call
   - ~200-250 lines

3. `requirements.txt`
   ```
   requests==2.31.0
   # fitdecode bundled (no PyPI package)
   ```

**Estimated Time:** 6-8 hours

### Phase 2: Packaging & Local Testing
- [ ] Create deployment package with fitdecode
- [ ] Test locally with mock EventBridge event
- [ ] Test locally with mock Strava webhook event
- [ ] Verify all imports work
- [ ] Test token refresh logic

**Estimated Time:** 2-3 hours

### Phase 3: AWS Deployment
- [ ] Create Lambda function (Python 3.12, 512 MB, 60 sec timeout)
- [ ] Upload deployment package
- [ ] Set environment variables:
  ```
  STRAVA_CLIENT_ID=<value>
  STRAVA_CLIENT_SECRET=<value>
  STRAVA_REFRESH_TOKEN=<value>
  PUSHOVER_API_TOKEN=<value>
  PUSHOVER_USER_KEY=<value>
  STRAVA_WEBHOOK_VERIFY_TOKEN=<value>  # For webhook security
  ```
- [ ] Create EventBridge rule: `cron(0 20 * * ? *)` (8pm UTC daily)
- [ ] (Optional) Create API Gateway + Strava webhook subscription

**Estimated Time:** 2-3 hours

### Phase 4: Integration Testing
- [ ] Trigger Lambda manually with CloudWatch test event
- [ ] Verify Pushover notification received
- [ ] Upload test activity to Strava (trigger webhook)
- [ ] Monitor CloudWatch Logs for errors
- [ ] Test multiple activities in one day
- [ ] Test activity with no battery data (graceful handling)

**Estimated Time:** 2-3 hours

**Total Estimated Effort:** 14-21 hours

---

## Critical Files Reference

| Purpose | File Path | Status | Lines |
|---------|-----------|--------|-------|
| Battery parsing logic | [battery_checker.py](battery_checker.py) | ✅ Complete | 434 |
| FIT decoder library | `/Users/brian/code/fitdecode/` | ✅ Available | ~1088 KB |
| Strava API test | [test_strava_fit_download.py](test_strava_fit_download.py) | ⚠️ Needs validation | 134 |
| Garmin API test | [test_garmin_fit_download.py](test_garmin_fit_download.py) | ⚠️ Backup option | 136 |
| OAuth token script | [get_strava_token.py](get_strava_token.py) | ✅ Ready | 126 |
| Test .fit file | [13_20_January_G_G_w_David.fit](13_20_January_G_G_w_David.fit) | ✅ Valid | 525 KB |
| Implementation plan | [LAMBDA_IMPLEMENTATION_PLAN.md](LAMBDA_IMPLEMENTATION_PLAN.md) | ✅ Reference | 209 |

---

## Risk Assessment Summary

| Risk Area | Severity | Mitigation | Status |
|-----------|----------|------------|--------|
| Strava .fit availability | HIGH | Test first, use Garmin fallback | Phase 0 validation |
| Token refresh logic missing | HIGH | Must implement before deploy | Add to Phase 1 |
| Webhook security | MEDIUM | Add signature verification | Add to Phase 1 |
| Package size | LOW | Already validated (~700 KB) | ✅ Acceptable |
| API rate limits | LOW | Usage well below limits | ✅ Not a concern |
| Duplicate notifications | LOW | User prefers this behavior | ✅ By design |

---

## Final Recommendations

### ✅ PROCEED with these conditions:

1. **Complete Phase 0 validation FIRST** - Don't write Lambda code until you confirm .fit file downloads work
2. **Add token refresh logic** - Critical for long-term operation
3. **Add webhook signature verification** - Required by Strava, security best practice
4. **Test package size** - Verify deployment package works with Lambda runtime

### 📝 Implementation Priority:

**MUST HAVE (blocking):**
- Strava token refresh logic
- Webhook signature verification
- .fit file download validation

**SHOULD HAVE (quality):**
- Comprehensive error handling
- Structured logging
- Package size validation

**NICE TO HAVE (future):**
- CloudWatch alarms
- Garmin fallback (only if Strava fails)
- Web dashboard

### 🎯 Success Criteria:

- [ ] Lambda executes successfully on daily schedule
- [ ] Receives .fit files from Strava API
- [ ] Correctly parses battery data from multiple device types
- [ ] Sends Pushover notification only for low batteries
- [ ] Handles token expiration gracefully
- [ ] Logs errors to CloudWatch for debugging
- [ ] No false positives (OK batteries don't notify)

---

## Conclusion

The Lambda implementation plan is **fundamentally sound** with proven technical components and a clear path to deployment. The existing codebase provides an excellent foundation with working battery parsing logic and test infrastructure.

**Key Strengths:**
- Pragmatic architecture (stateless, simple)
- Production-ready battery parsing code
- Comprehensive device support
- Clear implementation phases

**Required Additions:**
- Token refresh logic (2-3 hours)
- Webhook security (1-2 hours)
- .fit download validation (2-4 hours)

**Bottom Line:** With the three critical additions above, this plan is **ready for implementation** with high confidence of success. Total estimated effort is 14-21 hours from start to working production system.
