# PPOP Validation Implementation

## Overview

The HRSA RPA POC Application Validation Assistant (AVA) now supports **PPOP (Primary Place of Performance)** form validation in addition to SF-424 forms. This feature validates addresses using the **HRSA Data Warehouse (HDW) API** to ensure accurate geographic data for grant applications.

## Features

### Multi-Form Support
- **SF-424 Forms**: Original validation (UEI, FON, Grant Number, etc.)
- **PPOP Forms**: Address validation via HDW API
- **Automatic Form Detection**: System automatically identifies form type from PDF metadata and structure

### PPOP Address Validation
- Validates **Primary Site** address (required)
- Validates **Other Site** address (optional, if provided)
- Checks address against USPS records via HDW API
- Verifies congressional district accuracy
- Returns standardized address format

### Validation Status Codes

| HDW API Code | Description | Result |
|--------------|-------------|--------|
| **STD000** | Exact Match | ✅ PASS |
| **STD001** | Approximated Match | ✅ PASS (with warning) |
| **STD002** | Invalid Address | ❌ FAIL |
| **STD003** | Ambiguous Address | ❌ FAIL |

### Quality Checks
- ZIP+4 code present
- Street number validated
- Match score ≥ 95.0
- Match level: "01 - Point address" or "02 - Interpolated street address"

## Architecture

### Backend Components

#### 1. Form Type Detector (`services/form_type_detector.py`)
```python
class FormType(Enum):
    SF424 = "SF-424"
    PPOP_FORM = "PPOP"
    UNKNOWN = "UNKNOWN"
```

Detects form type by analyzing:
- PDF title: "Project/Performance Site Location(s)"
- XFA field patterns: `PerformanceSite_4_0_PrimarySite_*`
- Form-specific field indicators

#### 2. PPOP Field Mapper (`services/ppop_field_mapper.py`)
Extracts and maps PPOP address data:
- **Primary Site**: Organization, UEI, Street, City, State, ZIP, Congressional District
- **Other Site**: Same fields (optional)
- Parses state format: "VA: Virginia" → "VA"
- Parses ZIP format: "20166-6748" → ZIP5="20166", ZIP4="6748"

#### 3. PPOP Validator (`services/ppop_validator.py`)
Validates addresses via HDW API:
- Calls HDW API with address data
- Applies validation rules (STD000/001/002/003)
- Performs quality checks
- Compares congressional districts
- Returns validation errors with guidance

#### 4. Validation Error Factory
New PPOP-specific error types:
- `ppop_address_invalid()` - STD002 response
- `ppop_address_ambiguous()` - STD003 response
- `ppop_address_quality_failure()` - Quality check failures
- `ppop_district_mismatch()` - Congressional district mismatch
- `ppop_api_timeout()` - API timeout
- `ppop_api_error()` - API unavailable

### Frontend Components

#### Updated Components
- **AVAChatAssistant**: Handles form_type state
- **ChatInterface**: Displays form type in header chip

#### Display Format
```
[PPOP - filename.pdf] [PASSED/FAILED]
```

## Configuration

### Environment Variables

Add to `backend/.env`:

```env
# HDW API Configuration (PPOP Address Validation)
HDW_API_URL=https://data.hrsa.gov/HDWAPI3_External/api/Location/GetLocationInfoByAddress
HDW_API_TOKEN=your-hdw-api-token-here
HDW_API_TIMEOUT=30
HDW_API_ENABLED=true

# PPOP Validation Settings
PPOP_ACCEPT_APPROXIMATED_MATCH=true
PPOP_MINIMUM_MATCH_SCORE=95.0
PPOP_REQUIRE_ZIP4=true
PPOP_REQUIRE_STREET_NUMBER=true
```

### Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `HDW_API_URL` | HDW endpoint | HDW API URL |
| `HDW_API_TOKEN` | (required) | API authentication token |
| `HDW_API_TIMEOUT` | 30 | Request timeout in seconds |
| `HDW_API_ENABLED` | true | Enable/disable PPOP validation |
| `PPOP_ACCEPT_APPROXIMATED_MATCH` | true | Accept STD001 responses |
| `PPOP_MINIMUM_MATCH_SCORE` | 95.0 | Minimum match score (0-100) |
| `PPOP_REQUIRE_ZIP4` | true | Require ZIP+4 code |
| `PPOP_REQUIRE_STREET_NUMBER` | true | Require street number |

## Installation

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

New dependency: `requests==2.31.0`

### 2. Configure Environment

Copy `.env.example` to `.env` and add your HDW API token:

```bash
cp .env.example .env
# Edit .env and add HDW_API_TOKEN
```

### 3. Test Installation

```bash
python ../test_ppop_validation.py
```

## Usage

### Upload PPOP Form

1. Navigate to AVA application
2. Upload PPOP PDF form
3. System automatically detects form type
4. Validates addresses via HDW API
5. Displays validation results

### Validation Flow

```
PDF Upload
    ↓
Form Type Detection (PPOP vs SF-424)
    ↓
Extract Address Fields
    ├─ Primary Site (required)
    └─ Other Site (optional)
    ↓
HDW API Validation
    ├─ Address standardization
    ├─ Congressional district lookup
    └─ Quality checks
    ↓
Display Results
    ├─ ✅ Valid addresses
    ├─ ❌ Invalid addresses with guidance
    └─ ⚠️  Warnings (approximated, district mismatch)
```

### Example Validation Results

#### Success
```
✅ PPOP Form has passed the validations

Addresses validated successfully:
   ✅ Primary Site: 45335 Vintage Park Plz, Sterling, VA 20166-6748
      Congressional District: VA-010
   ✅ Other Site: 45335 Vintage Prk Plz, Sterling, VA 20166-6111
      Congressional District: VA-001
```

#### Failure
```
❌ Primary Site address could not be validated.

• Verify the address in the PPOP form is correct
• Check for typos in street number, street name, city, or ZIP code
• Ensure the address is a valid, deliverable location
• Confirm the address exists in USPS records
```

## API Integration

### HDW API Request Format

```json
{
  "InputAddresses": [{
    "inputAddress": "45335 Vintage Park Plaza",
    "inputCity": "Sterling",
    "inputState": "VA",
    "inputZip": "20166",
    "inputTieBreaker": "True"
  }],
  "Targets": "CONGDIST,COUNTY",
  "token": "YOUR_API_TOKEN"
}
```

### HDW API Response Format

```json
{
  "Addresses": [{
    "code": "STD000",
    "description": "Exact Match",
    "street": "45335 Vintage Park Plz",
    "city": "Sterling",
    "state": "VA",
    "zip5Code": "20166",
    "zip4Code": "6748",
    "StreetNumber": "45335",
    "score": 100.0,
    "Locations": [{
      "matchLevel": "01 - Point address"
    }],
    "Targets": [
      {
        "Target": "COUNTY",
        "Preferred": [{
          "County Name": "Loudoun",
          "State County FIPS Code": "51107"
        }]
      },
      {
        "Target": "CONGDIST",
        "Preferred": [{
          "Congressional District Code": "VA10"
        }]
      }
    ]
  }]
}
```

## Error Handling

### API Downtime
If HDW API is unavailable:
- Displays user-friendly error message
- Allows SF-424 validation to continue
- Suggests trying again later

### Invalid Form Type
If uploaded PDF is neither SF-424 nor PPOP:
- Rejects upload immediately
- Shows error: "Unsupported form type. Please upload an SF-424 or PPOP form."

### Validation Errors
Each error includes:
- **User Message**: Clear, actionable description
- **Field Location**: Where to find the field in the form
- **Current Value**: What was entered
- **Guidance**: Step-by-step fix instructions
- **AI Context**: Technical details for AI assistant

## Testing

### Test Script

Run the test suite:

```bash
python test_ppop_validation.py
```

Tests include:
1. **Form Type Detection**: Verify PPOP form is detected correctly
2. **Field Extraction**: Verify address fields are extracted properly
3. **PPOP Validation**: Verify HDW API integration works
4. **SF-424 Detection**: Verify SF-424 forms are not detected as PPOP

### Test Data

- `PPOP_TestData.pdf`: Single address (Primary Site only)
- `PPOP_TestData - 2.pdf`: Multiple addresses (Primary + Other Site)

### Manual Testing

1. Upload PPOP form with valid address
   - Expected: ✅ PASS with standardized address
2. Upload PPOP form with invalid address
   - Expected: ❌ FAIL with guidance
3. Upload SF-424 form
   - Expected: SF-424 validation (not PPOP)
4. Upload non-form PDF
   - Expected: Rejection with error message

## Troubleshooting

### "HDW API is down"
- Check `HDW_API_ENABLED=true` in `.env`
- Verify `HDW_API_TOKEN` is correct
- Test API connectivity: `curl -X POST [HDW_API_URL]`

### "Unsupported form type"
- Verify PDF is a valid PPOP or SF-424 form
- Check PDF title contains "Project/Performance Site Location"
- Ensure PDF has XFA form fields

### "Address validation timeout"
- Increase `HDW_API_TIMEOUT` in `.env`
- Check network connectivity
- Verify HDW API is operational

### Congressional District Mismatch
- This is a warning, not an error
- HDW API result takes precedence
- User should verify which district is correct

## Future Enhancements

- [ ] Support for additional form types
- [ ] Batch address validation
- [ ] Address history tracking
- [ ] Geographic visualization of addresses
- [ ] Integration with additional geocoding APIs
- [ ] Offline address validation fallback

## References

- [PPOP Validation Implementation Guide](./PPOP_Validation_Implementation_Guide.md)
- [HDW API Documentation](https://data.hrsa.gov/)
- [SF-424 Form Specifications](https://www.grants.gov/web/grants/forms/sf-424-family.html)

## Support

For issues or questions:
1. Check this documentation
2. Review test script output
3. Check backend logs for detailed error messages
4. Contact HRSA support for HDW API issues
