Shader "Skybox/Grid"
{
    Properties
    {
        [Header(Colors)]
        _TopColor ("Top Color", Color) = (0.05, 0.05, 0.15, 1)
        _HorizonColor ("Horizon Color", Color) = (0.1, 0.3, 0.5, 1)
        _BottomColor ("Bottom Color", Color) = (0.0, 0.1, 0.2, 1)

        [Header(Grid)]
        _GridColor ("Grid Color", Color) = (0, 0.8, 1, 1)
        _GridColor2 ("Grid Color 2", Color) = (1, 0.3, 0.8, 1)
        _GridSize ("Grid Size", Float) = 10.0
        _GridIntensity ("Grid Intensity", Range(0, 2)) = 0.8
        _GridLineWidth ("Grid Line Width", Range(0.01, 0.5)) = 0.1

        [Header(Glow)]
        _GlowIntensity ("Glow Intensity", Range(0, 5)) = 2.0
        _PulseSpeed ("Pulse Speed", Float) = 1.0

        [Header(Stars)]
        _StarDensity ("Star Density", Range(0, 1)) = 0.3
        _StarBrightness ("Star Brightness", Range(0, 2)) = 1.0
    }

    SubShader
    {
        Tags { "Queue"="Background" "RenderType"="Background" "PreviewType"="Skybox" }
        Cull Off
        ZWrite Off

        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            struct appdata
            {
                float4 vertex : POSITION;
                float3 uv : TEXCOORD0;
            };

            struct v2f
            {
                float4 position : SV_POSITION;
                float3 viewDir : TEXCOORD0;
            };

            float4 _TopColor;
            float4 _HorizonColor;
            float4 _BottomColor;
            float4 _GridColor;
            float4 _GridColor2;
            float _GridSize;
            float _GridIntensity;
            float _GridLineWidth;
            float _GlowIntensity;
            float _PulseSpeed;
            float _StarDensity;
            float _StarBrightness;

            v2f vert (appdata v)
            {
                v2f o;
                o.position = UnityObjectToClipPos(v.vertex);
                o.viewDir = v.uv;
                return o;
            }

            // Hash function for pseudo-random noise
            float hash(float3 p)
            {
                p = frac(p * 0.3183099 + 0.1);
                p *= 17.0;
                return frac(p.x * p.y * p.z * (p.x + p.y + p.z));
            }

            float hash2(float2 p)
            {
                return frac(sin(dot(p, float2(127.1, 311.7))) * 43758.5453123);
            }

            // Improved stars using 3D cell space to avoid stretching
            float stars(float3 viewDir, float density)
            {
                // Use view direction directly in 3D space
                float3 p = viewDir * 50.0; // Scale for star distribution
                float3 cellPos = floor(p);
                float3 localPos = frac(p);

                float starValue = 0.0;

                // Check neighboring cells
                for(int x = -1; x <= 1; x++)
                {
                    for(int y = -1; y <= 1; y++)
                    {
                        for(int z = -1; z <= 1; z++)
                        {
                            float3 offset = float3(x, y, z);
                            float3 cell = cellPos + offset;
                            float h = hash(cell);

                            if(h < density)
                            {
                                // Random position within cell
                                float3 starPos = offset + float3(
                                    hash(cell + 1.0),
                                    hash(cell + 2.0),
                                    hash(cell + 3.0)
                                );

                                float dist = length(localPos - starPos);

                                // Twinkle effect
                                float twinkle = 0.7 + 0.3 * sin(_Time.y * _PulseSpeed * 2.0 + h * 6.28);

                                // Size variation
                                float size = 0.015 + hash(cell + 4.0) * 0.025;

                                // Smooth star with glow
                                float star = smoothstep(size, 0.0, dist);
                                star += smoothstep(size * 3.0, 0.0, dist) * 0.3; // Outer glow

                                starValue += star * twinkle;
                            }
                        }
                    }
                }
                return saturate(starValue);
            }

            fixed4 frag (v2f i) : SV_Target
            {
                float3 viewDir = normalize(i.viewDir);

                // Gradient from top to bottom
                float verticalGradient = viewDir.y;
                float horizonGradient = 1.0 - abs(viewDir.y);

                // Sky gradient
                float4 skyColor = lerp(_BottomColor, _HorizonColor, saturate(verticalGradient + 0.5));
                skyColor = lerp(skyColor, _TopColor, saturate(verticalGradient));

                // Add horizon glow
                float horizonGlow = pow(horizonGradient, 3.0) * 0.5;
                skyColor.rgb += _HorizonColor.rgb * horizonGlow;

                // Grid on lower hemisphere
                float gridMask = saturate(-viewDir.y * 2.0);

                if(gridMask > 0.01)
                {
                    // Project onto ground plane
                    float3 gridPos = viewDir / max(abs(viewDir.y), 0.01);
                    float2 grid2D = gridPos.xz / _GridSize;

                    // Calculate grid lines
                    float2 derivative = fwidth(grid2D);
                    float2 gridVal = abs(frac(grid2D - 0.5) - 0.5) / derivative;
                    float gridDist = min(gridVal.x, gridVal.y);

                    // Anti-aliased grid lines
                    float gridLine = 1.0 - smoothstep(0.0, _GridLineWidth * 2.0, gridDist);

                    // Distance fade
                    float distFade = saturate(1.0 - length(grid2D) * 0.05);

                    // Animated pulse
                    float pulse = 0.5 + 0.5 * sin(_Time.y * _PulseSpeed);

                    // Alternate grid colors
                    float colorSwitch = step(0.5, frac(floor(grid2D.x / 5.0) + floor(grid2D.y / 5.0)));
                    float4 activeGridColor = lerp(_GridColor, _GridColor2, colorSwitch);

                    // Apply grid with glow
                    float gridGlow = gridLine * _GlowIntensity * distFade * (0.7 + 0.3 * pulse);
                    skyColor.rgb += activeGridColor.rgb * gridGlow * gridMask;
                }

                // Add stars to upper hemisphere
                if(viewDir.y > 0.0)
                {
                    float starField = stars(viewDir, _StarDensity);
                    float starMask = saturate(viewDir.y * 2.0); // Fade near horizon
                    skyColor.rgb += starField * _StarBrightness * _GridColor.rgb * starMask;
                }

                return skyColor;
            }
            ENDCG
        }
    }
}
