#Bash command to get access token

curl -X POST https://www.strava.com/oauth/token \
>   -d client_id=$STRAVA_CLIENT_ID \
>   -d client_secret=$STRAVA_CLIENT_SECRET \
>   -d grant_type=refresh_token \
>   -d refresh_token=$STRAVA_REFRESH_TOKEN