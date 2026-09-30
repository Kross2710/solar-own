import React from "react";

interface HouseProps {
    pvWatt: number;
    houseWatt: number;
    battWatt: number;
    gridWatt: number;
    battSoc: number;
    solarState: string;
}

export default function IsometricHouse({
    pvWatt,
    houseWatt,
    battWatt,
    gridWatt,
    battSoc,
    solarState,
}: HouseProps) {
    // Điều kiện kích hoạt các luồng comet
    const hasSolar = pvWatt > 20;
    const isCharging = battWatt > 20;
    const isDischarging = battWatt < -20;
    const isHouseConsuming = houseWatt > 20;
    const isGridImport = gridWatt > 20;
    const isGridExport = gridWatt < -20;

    battWatt = Math.abs(battWatt); // Chuyển đổi giá trị watt pin sang dương để hiển thị
    gridWatt = Math.abs(gridWatt); // Chuyển đổi giá trị watt lưới sang dương để hiển thị

    // Dữ liệu hiển thị dynamic theo kW nếu >= 1000W
    function formatWatt(value: number): string {
        if (Math.abs(value) >= 1000) {
            return `${(value / 1000).toFixed(2)} kW`;
        }
        return `${value} W`;
    }

    return (
        <div className="relative w-full max-w-[420px] mx-auto select-none">
            <svg className="w-full h-auto block" viewBox="0 0 360 320" aria-hidden="true">
                <defs>
                    <radialGradient id="hsShadow" cx="50%" cy="50%" r="50%">
                        <stop offset="0%" stopColor="rgba(0,0,0,.55)" />
                        <stop offset="100%" stopColor="rgba(0,0,0,0)" />
                    </radialGradient>

                    {/* Đuôi comet */}
                    <linearGradient id="ctPv">
                        <stop offset="0" stopColor="#ffc76b" stopOpacity="0" />
                        <stop offset="1" stopColor="#ffc76b" stopOpacity=".85" />
                    </linearGradient>
                    <linearGradient id="ctLoad">
                        <stop offset="0" stopColor="#7dd3fc" stopOpacity="0" />
                        <stop offset="1" stopColor="#7dd3fc" stopOpacity=".85" />
                    </linearGradient>
                    <linearGradient id="ctBatt">
                        <stop offset="0" stopColor="#b8a6ff" stopOpacity="0" />
                        <stop offset="1" stopColor="#b8a6ff" stopOpacity=".85" />
                    </linearGradient>
                    <linearGradient id="ctIn">
                        <stop offset="0" stopColor="#fb8a95" stopOpacity="0" />
                        <stop offset="1" stopColor="#fb8a95" stopOpacity=".85" />
                    </linearGradient>
                    <linearGradient id="ctOut">
                        <stop offset="0" stopColor="#34d399" stopOpacity="0" />
                        <stop offset="1" stopColor="#34d399" stopOpacity=".85" />
                    </linearGradient>

                    {/* Quầng sáng comet */}
                    <radialGradient id="hlPv">
                        <stop offset="0" stopColor="#ffc76b" stopOpacity=".4" />
                        <stop offset="100%" stopColor="#ffc76b" stopOpacity="0" />
                    </radialGradient>
                    <radialGradient id="hlLoad">
                        <stop offset="0" stopColor="#7dd3fc" stopOpacity=".4" />
                        <stop offset="100%" stopColor="#7dd3fc" stopOpacity="0" />
                    </radialGradient>
                    <radialGradient id="hlBatt">
                        <stop offset="0" stopColor="#b8a6ff" stopOpacity=".4" />
                        <stop offset="100%" stopColor="#b8a6ff" stopOpacity="0" />
                    </radialGradient>
                    <radialGradient id="hlIn">
                        <stop offset="0" stopColor="#fb8a95" stopOpacity=".4" />
                        <stop offset="100%" stopColor="#fb8a95" stopOpacity="0" />
                    </radialGradient>
                    <radialGradient id="hlOut">
                        <stop offset="0" stopColor="#34d399" stopOpacity=".4" />
                        <stop offset="100%" stopColor="#34d399" stopOpacity="0" />
                    </radialGradient>

                    {/* Đường dẫn dòng chảy */}
                    <path id="hp1f" d="M196,166 L196,228 Q196,234 190.6,236.7 L185.4,239.3 Q180,242 174.6,239.4 L137,221" />
                    <path id="hp1h" d="M196,166 L196,234" />
                    <path id="hp1r" d="M137,221 L174.6,239.4 Q180,242 185.4,239.3 L196,234" />
                    <path id="hp2f" d="M196,234 L235.8,214.5 Q243,211 243,203 L243,192" />
                    <path id="hp3f" d="M196,236 L196,250 Q196,258 204,258 L298,258" />
                    <path id="hp3r" d="M298,258 L204,258 Q196,258 196,250 L196,236" />
                </defs>

                {/* Khung nhà 3D Isometric */}
                <ellipse cx="185" cy="252" rx="145" ry="34" fill="url(#hsShadow)" />
                <polygon points="180,242 75,190 75,122 127.5,108 180,174" fill="#262a31" />
                <polygon points="180,242 285,190 285,122 180,174" fill="#1b1e24" />
                <polygon points="180,174 285,122 232.5,56 127.5,108" fill="#14171d" />
                <line x1="127.5" y1="108" x2="232.5" y2="56" stroke="rgba(255,255,255,.09)" strokeWidth="1.5" />
                <line x1="180" y1="174" x2="180" y2="242" stroke="rgba(255,255,255,.05)" strokeWidth="1" />

                {/* Mảng pin trên mái */}
                <g transform="matrix(105,-52,-52.5,-66,180,174)">
                    <rect x="0.06" y="0.1" width="0.88" height="0.82" fill="#0b111c" />
                    <rect x="0.09" y="0.15" width="0.19" height="0.22" fill="#1c2a40" />
                    <rect x="0.303" y="0.15" width="0.19" height="0.22" fill="#1c2a40" />
                    <rect x="0.516" y="0.15" width="0.19" height="0.22" fill="#1c2a40" />
                    <rect x="0.729" y="0.15" width="0.19" height="0.22" fill="#1c2a40" />
                    <rect x="0.09" y="0.41" width="0.19" height="0.22" fill="#1c2a40" />
                    <rect x="0.303" y="0.41" width="0.19" height="0.22" fill="#1c2a40" />
                    <rect x="0.516" y="0.41" width="0.19" height="0.22" fill="#1c2a40" />
                    <rect x="0.729" y="0.41" width="0.19" height="0.22" fill="#1c2a40" />
                    <rect x="0.09" y="0.67" width="0.19" height="0.22" fill="#1c2a40" />
                    <rect x="0.303" y="0.67" width="0.19" height="0.22" fill="#1c2a40" />
                    <rect x="0.516" y="0.67" width="0.19" height="0.22" fill="#1c2a40" />
                    <rect x="0.729" y="0.67" width="0.19" height="0.22" fill="#1c2a40" />
                </g>

                {/* Cửa sổ & Cửa ra vào */}
                <g transform="matrix(105,-52,0,-68,180,242)">
                    <rect x="0.52" y="0.42" width="0.16" height="0.3" fill="#f2e7c4" opacity="0.95" />
                    <rect x="0.595" y="0.42" width="0.012" height="0.3" fill="#1b1e24" />
                    <rect x="0.52" y="0.56" width="0.16" height="0.018" fill="#1b1e24" />
                    <rect x="0.74" y="0.42" width="0.16" height="0.3" fill="#f2e7c4" opacity="0.95" />
                    <rect x="0.815" y="0.42" width="0.012" height="0.3" fill="#1b1e24" />
                    <rect x="0.74" y="0.56" width="0.16" height="0.018" fill="#1b1e24" />
                    <rect x="0.14" y="0" width="0.14" height="0.5" fill="#121419" />
                </g>

                {/* Pin treo tường */}
                <g transform="matrix(-105,-52,0,-68,180,242)">
                    <rect x="0.32" y="0.06" width="0.18" height="0.58" fill="#e6e9ee" />
                    <rect
                        x="0.32"
                        y="0.06"
                        width="0.18"
                        height={0.58 * Math.max(0, Math.min(1, battSoc / 100))}
                        fill={battSoc <= 20 ? "#ef4444" : battSoc <= 50 ? "#fbbf24" : "#34d399"}
                    />
                    <rect x="0.32" y="0.06" width="0.03" height="0.58" fill="rgba(0,0,0,.12)" />
                </g>

                {/* Các đường ống dẫn tĩnh */}
                <path d="M196,166 L196,234 L180,242 L137,221" fill="none" stroke="rgba(255,255,255,0.09)" strokeWidth="2.5" strokeLinecap="round" />
                <path d="M196,234 L243,211 L243,192" fill="none" stroke="rgba(255,255,255,0.09)" strokeWidth="2.5" strokeLinecap="round" />
                <path d="M196,236 L196,258 L298,258" fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="2.5" strokeLinecap="round" />

                {/* Luồng 1: Solar -> Pin */}
                {hasSolar && isCharging && (
                    <g>
                        {[0, -1, -2].map((begin, idx) => (
                            <g key={idx}>
                                <circle r="6.5" fill="url(#hlPv)" />
                                <rect x="-11" y="-1.6" width="11" height="3.2" rx="1.6" fill="url(#ctPv)" />
                                <circle r="2.3" fill="#ffc76b" />
                                <animateMotion dur="3s" begin={`${begin}s`} repeatCount="indefinite" rotate="auto">
                                    <mpath href="#hp1f" />
                                </animateMotion>
                            </g>
                        ))}
                    </g>
                )}

                {/* Bổ sung: Nếu ban ngày đầy pin, Solar -> House */}
                {hasSolar && !isCharging && isHouseConsuming && (
                    <g>
                        {[0, -1, -2].map((begin, idx) => (
                            <g key={idx}>
                                <circle r="6.5" fill="url(#hlPv)" />
                                <rect x="-11" y="-1.6" width="11" height="3.2" rx="1.6" fill="url(#ctPv)" />
                                <circle r="2.3" fill="#ffc76b" />
                                <animateMotion dur="3s" begin={`${begin}s`} repeatCount="indefinite" rotate="auto">
                                    <mpath href="#hp1h" />
                                </animateMotion>
                            </g>
                        ))}
                    </g>
                )}

                {/* Luồng 2: Pin xả -> Tải */}
                {isDischarging && (
                    <g>
                        {[0, -0.75].map((begin, idx) => (
                            <g key={idx}>
                                <circle r="6.5" fill="url(#hlBatt)" />
                                <rect x="-11" y="-1.6" width="11" height="3.2" rx="1.6" fill="url(#ctBatt)" />
                                <circle r="2.3" fill="#b8a6ff" />
                                <animateMotion dur="1.5s" begin={`${begin}s`} repeatCount="indefinite" rotate="auto">
                                    <mpath href="#hp1r" />
                                </animateMotion>
                            </g>
                        ))}
                    </g>
                )}

                {/* Luồng 3: Cấp điện vào nhà */}
                {isHouseConsuming && (
                    <g>
                        {[0, -0.8].map((begin, idx) => (
                            <g key={idx}>
                                <circle r="6.5" fill="url(#hlLoad)" />
                                <rect x="-11" y="-1.6" width="11" height="3.2" rx="1.6" fill="url(#ctLoad)" />
                                <circle r="2.3" fill="#7dd3fc" />
                                <animateMotion dur="1.6s" begin={`${begin}s`} repeatCount="indefinite" rotate="auto">
                                    <mpath href="#hp2f" />
                                </animateMotion>
                            </g>
                        ))}
                    </g>
                )}

                {/* Luồng 4: Nhập lưới (Grid Import) */}
                {isGridImport && (
                    <g>
                        {[0, -0.9, -1.8].map((begin, idx) => (
                            <g key={idx}>
                                <circle r="6.5" fill="url(#hlIn)" />
                                <rect x="-11" y="-1.6" width="11" height="3.2" rx="1.6" fill="url(#ctIn)" />
                                <circle r="2.3" fill="#fb8a95" />
                                <animateMotion dur="2.7s" begin={`${begin}s`} repeatCount="indefinite" rotate="auto">
                                    <mpath href="#hp3r" />
                                </animateMotion>
                            </g>
                        ))}
                    </g>
                )}

                {/* Luồng 5: Phát ngược lưới (Grid Export) */}
                {isGridExport && (
                    <g>
                        {[0, -0.9, -1.8].map((begin, idx) => (
                            <g key={idx}>
                                <circle r="6.5" fill="url(#hlOut)" />
                                <rect x="-11" y="-1.6" width="11" height="3.2" rx="1.6" fill="url(#ctOut)" />
                                <circle r="2.3" fill="#34d399" />
                                <animateMotion dur="2.7s" begin={`${begin}s`} repeatCount="indefinite" rotate="auto">
                                    <mpath href="#hp3f" />
                                </animateMotion>
                            </g>
                        ))}
                    </g>
                )}
            </svg>

            {/* Callouts (Toạ độ chuẩn từ bản thiết kế chuyển sang Tailwind) */}

            {/* 1. Solar Callout */}
            <div className="absolute left-[50.2%] top-2 -translate-x-1/2 text-center whitespace-nowrap z-10">
                <div className="text-sm md:text-base font-bold text-amber-300 tabular-nums">{formatWatt(pvWatt)}</div>
                <div className="text-[10px] font-bold tracking-widest uppercase text-zinc-400">Solar</div>
            </div>
            <div className="absolute left-[50.2%] top-[10.5%] h-[23%] w-px bg-white/20 -translate-x-1/2" />

            {/* 2. Home Callout */}
            <div className="absolute left-[74%] top-2 -translate-x-1/2 text-center whitespace-nowrap z-10">
                <div className="text-sm md:text-base font-bold text-sky-300 tabular-nums">{formatWatt(houseWatt)}</div>
                <div className="text-[10px] font-bold tracking-widest uppercase text-zinc-400">Home</div>
            </div>
            <div className="absolute left-[74%] top-[10.5%] h-[38%] w-px bg-white/20 -translate-x-1/2" />

            {/* 3. Battery Callout */}
            <div className="absolute left-[38.1%] bottom-2 -translate-x-1/2 text-center whitespace-nowrap z-10">
                <div className="text-sm md:text-base font-bold text-purple-300 tabular-nums">
                    <span>{formatWatt(battWatt)}</span>
                    {battSoc > 0 && <span className="text-purple-400 ml-1 text-xs">· {battSoc}%</span>}
                </div>
                <div className="text-[10px] font-bold tracking-widest uppercase text-zinc-400">Battery</div>
            </div>
            <div className="absolute left-[38.1%] top-[70%] h-[16%] w-px bg-white/20 -translate-x-1/2" />

            {/* 4. Grid Callout */}
            <div className={`absolute left-[83.3%] bottom-2 -translate-x-1/2 text-center whitespace-nowrap z-10 transition-opacity ${Math.abs(gridWatt) < 10 ? "opacity-50" : "opacity-100"}`}>
                <div className={`text-sm md:text-base font-bold tabular-nums ${gridWatt > 0 ? "text-rose-300" : gridWatt < 0 ? "text-emerald-300" : "text-zinc-300"}`}>
                    {formatWatt(gridWatt)}
                </div>
                <div className="text-[10px] font-bold tracking-widest uppercase text-zinc-400">
                    {gridWatt < -10 ? "Export" : "Grid"}
                </div>
            </div>
            <div className="absolute left-[83.3%] top-[82%] h-[6%] w-px bg-white/20 -translate-x-1/2" />

            {/* 5. Status Callout (Generating, Idle, Discharging), on the top left of the house */}
            <div className="absolute left-[18%] top-2 -translate-x-1/2 text-center whitespace-nowrap z-10">
                <div className="text-sm md:text-base font-bold text-amber-300 tabular-nums">{solarState}</div>
            </div>
        </div>
    );
}