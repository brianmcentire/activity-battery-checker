SIMULATOR_ID = FC5A5656-2432-4B29-974B-22605B44EA29
IOS_PROJECT = ios/ActivityBatteryChecker
IOS_SCHEME = ActivityBatteryChecker
IOS_BUNDLE = com.activitybatterychecker.ActivityBatteryChecker
IOS_APP = $(shell find ~/Library/Developer/Xcode/DerivedData/ActivityBatteryChecker-*/Build/Products/Debug-iphonesimulator/ActivityBatteryChecker.app -maxdepth 0 2>/dev/null | head -1)

.PHONY: test server ios-generate ios-build ios-run ios

test:
	python3 -m pytest tests/ -v

server:
	uvicorn app.main:app --reload

ios-generate:
	cd $(IOS_PROJECT) && xcodegen generate

ios-build: ios-generate
	xcodebuild -project $(IOS_PROJECT)/$(IOS_SCHEME).xcodeproj \
		-scheme $(IOS_SCHEME) \
		-destination 'platform=iOS Simulator,id=$(SIMULATOR_ID)' \
		build

ios-run: ios-build
	xcrun simctl boot $(SIMULATOR_ID) 2>/dev/null || true
	open -a Simulator
	xcrun simctl install $(SIMULATOR_ID) "$(IOS_APP)"
	xcrun simctl launch $(SIMULATOR_ID) $(IOS_BUNDLE)

ios: ios-run
