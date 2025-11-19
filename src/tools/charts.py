"""
Chart-related tools for the FMP MCP server

This module contains tools related to the Chart section of the Financial Modeling Prep API:
https://site.financialmodelingprep.com/developer/docs/stable#charts
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List

from src.api.client import fmp_api_request
from src.tools.statements import format_number
from src.prompts.model import DisplayMeta


async def get_price_change(symbol: str, display_name: str = '', description: str = '') -> str:
    """
    Get price changes for a stock based on historical data
    
    Args:
        symbol: Stock ticker symbol (e.g., AAPL, MSFT)
        display_name (str): Please provide a short and context related name for the purpose of displaying this tool call on ui, verb + noun (<= 30 characters and 3 words)
        description (str): Have the LLM provide the reasons and evidence for invoking this method
    Returns:
        Price changes over recent time periods
    """
    # Use the stable historical price endpoint from Chart section
    data = await fmp_api_request("historical-price-eod/light", {"symbol": symbol})
    
    if isinstance(data, dict) and "error" in data:
        return f"Error fetching price change for {symbol}: {data.get('message', 'Unknown error')}"
    
    # Process the historical data to calculate price changes
    historical_entries = []
    
    # Handle different response formats
    if isinstance(data, dict) and "historical" in data:
        if not data["historical"] or len(data["historical"]) == 0:
            return f"No historical price data found for symbol {symbol}"
        historical_entries = data["historical"]
    elif isinstance(data, list) and len(data) > 0:
        historical_entries = data
    else:
        return f"No historical price data found for symbol {symbol}"
    
    # Sort by date (most recent first)
    historical_entries.sort(key=lambda x: x.get('date', ''), reverse=True)
    
    # Get the latest price 
    if not historical_entries:
        return f"No historical price data available for {symbol}"
    
    latest_entry = historical_entries[0]
    latest_price = latest_entry.get('close', latest_entry.get('price', None))
    
    if latest_price is None:
        return f"Price data not available for {symbol}"
    
    # Format the response
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    result = [f"# Price History for {symbol}", f"*Data as of {current_time}*", ""]
    result.append(f"**Latest Price**: ${format_number(latest_price)} on {latest_entry.get('date', 'unknown date')}")
    result.append("")
    
    # Calculate some basic price changes if we have enough history
    if len(historical_entries) >= 30:
        try:
            # 1 day change (if available)
            if len(historical_entries) >= 2:
                prev_day = historical_entries[1]
                prev_price = prev_day.get('close', prev_day.get('price', None))
                if prev_price:
                    day_change = ((latest_price - prev_price) / prev_price) * 100
                    emoji = "🔺" if day_change > 0 else "🔻" if day_change < 0 else "➖"
                    result.append(f"**1 Day Change**: {emoji} {day_change:.2f}%")
            
            # 1 week change (approximately 5 trading days)
            if len(historical_entries) >= 6:
                week_entry = historical_entries[5]
                week_price = week_entry.get('close', week_entry.get('price', None))
                if week_price:
                    week_change = ((latest_price - week_price) / week_price) * 100
                    emoji = "🔺" if week_change > 0 else "🔻" if week_change < 0 else "➖"
                    result.append(f"**1 Week Change**: {emoji} {week_change:.2f}%")
            
            # 1 month change (approximately 21 trading days)
            if len(historical_entries) >= 22:
                month_entry = historical_entries[21]
                month_price = month_entry.get('close', month_entry.get('price', None))
                if month_price:
                    month_change = ((latest_price - month_price) / month_price) * 100
                    emoji = "🔺" if month_change > 0 else "🔻" if month_change < 0 else "➖"
                    result.append(f"**1 Month Change**: {emoji} {month_change:.2f}%")
            
        except (TypeError, ValueError, ZeroDivisionError) as e:
            # Handle any calculation errors gracefully
            result.append(f"**Note**: Some price changes could not be calculated")
    else:
        result.append("*Insufficient historical data for price change calculations*")
    
    return "\n".join(result)


async def get_historical_price(
    symbol: str,
    display_name: str = '',
    description: str = '',
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
) -> str:
    """
    Get historical end-of-day price data (stocks, crypto, or commodities).
    
    This tool is suitable for:
    - Quickly checking how a ticker traded around a specific date or short period
    - Looking at recent price action when analyzing a user's past trades
    - Fetching a compact window of prices to avoid overloading the context
    
    Args:
        symbol (str):
            The instrument symbol, e.g.:
            - Stock: "AAPL", "MSFT"
            - Crypto: "BTCUSD"
            - Commodity / index: "GCUSD", "^GSPC"
        display_name (str): Please provide a short and context related name for the purpose of displaying this tool call on ui, verb + noun (<= 30 characters and 3 words)
        description (str): Have the LLM provide the reasons and evidence for invoking this method
        from_date: Optional start date in format "YYYY-MM-DD"
        to_date: Optional end date in format "YYYY-MM-DD"
    Returns:
        Historical price data formatted as markdown
    """
    # Validate parameters
    if not symbol:
        return "Error: Symbol parameter is required"
    
    # Prepare parameters
    params = {"symbol": symbol}
    
    today = datetime.now(tz=timezone.utc).date()

    if to_date is None:
        to_date = today.strftime("%Y-%m-%d")
    
    if from_date is None:
        # Default: 5 days before today
        five_days_ago = today - timedelta(days=5)
        from_date = five_days_ago.strftime("%Y-%m-%d")
        
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date

    # Make API request
    data = await fmp_api_request("historical-price-eod/full", params)
    
    # Check for errors
    if isinstance(data, dict) and "error" in data:
        return f"Error fetching historical price data: {data.get('message', 'Unknown error')}"
    
    # Check for empty response
    if not data or not isinstance(data, list) or len(data) == 0:
        return f"No historical price data found for {symbol}"
    
    # Format the response
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    result = [
        f"# Historical Price Data for {symbol}",
        f"*Data as of {current_time}*",
    ]
    
    # Add date range info if provided
    if from_date and to_date:
        result.append(f"From: {from_date} To: {to_date}")
    elif from_date:
        result.append(f"From: {from_date}")
    elif to_date:
        result.append(f"To: {to_date}")
    
    # Add table header
    result.extend([
        "",
        "| Date | Open | High | Low | Close | Volume | Change | Change % | VWAP |",
        "|------|------|------|-----|-------|--------|--------|----------|------|"
    ])

    # Sort data by date (newest first)
    sorted_data = sorted(data, key=lambda x: x.get('date', ''), reverse=True)

    # Process each data point and format row
    for entry in sorted_data:
        date = entry.get('date', 'N/A')
        open = format_number(entry.get('open', 'N/A'))
        high = format_number(entry.get('high', 'N/A'))
        low = format_number(entry.get('low', 'N/A'))
        close = format_number(entry.get('close', 'N/A'))
        volume = format_number(entry.get('volume', 'N/A'))
        change = format_number(entry.get('change', 'N/A'))
        change_percent = format_number(entry.get('changePercent', 'N/A'))
        vwap = format_number(entry.get('vwap', 'N/A'))

        # Add to results
        result.append(f"| {date} | {open} | {high} | {low} | {close} | {volume} | {change} | {change_percent}% | {vwap} |")

    # Add a note about usage
    result.extend([
        "",
        f"*Note: Historical price data shows the closing price for {symbol} on each trading day.*"
    ])
    
    return "\n".join(result)