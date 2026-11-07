
import React, { useState } from 'react'

interface Job {
  title: string
  company: string
  location: string
  url: string
  description: string
  source: string

  ats_score?: number
  semantic_score?: number
  combined_score?: number

  matched_skills?: string[]
  missing_skills?: string[]
  other_resume_skills?: string[]

  resume_skill_count?: number
  job_skill_count?: number

  job_requirement_coverage?: number | null
  candidate_skill_coverage?: number | null
}

const ScoreBadge: React.FC<{
  label: string
  score: number
  colorClass: string
}> = ({ label, score, colorClass }) => (
  <div className="flex flex-col items-center">
    <span className="text-[10px] text-slate-500 uppercase tracking-widest mb-0.5">
      {label}
    </span>
    <span className={`text-sm font-bold px-2 py-0.5 rounded-full ${colorClass}`}>
      {score.toFixed(0)}%
    </span>
  </div>
)

function getScoreColors(score: number) {
  if (score >= 65) {
    return {
      badge: 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30',
      ring: 'text-emerald-400',
    }
  }

  if (score >= 45) {
    return {
      badge: 'bg-amber-500/20 text-amber-300 border border-amber-500/30',
      ring: 'text-amber-400',
    }
  }

  if (score >= 25) {
    return {
      badge: 'bg-orange-500/20 text-orange-300 border border-orange-500/30',
      ring: 'text-orange-400',
    }
  }

  return {
    badge: 'bg-slate-600/50 text-slate-400 border border-slate-600',
    ring: 'text-slate-400',
  }
}

function getSourceColor(source: string) {
  const s = source.toLowerCase()

  if (s.includes('linkedin')) return 'bg-blue-900/40 text-blue-300 border-blue-700/40'
  if (s.includes('indeed')) return 'bg-violet-900/40 text-violet-300 border-violet-700/40'
  if (s.includes('internshala')) return 'bg-cyan-900/40 text-cyan-300 border-cyan-700/40'
  if (s.includes('naukri')) return 'bg-pink-900/40 text-pink-300 border-pink-700/40'
  if (s.includes('yc') || s.includes('startup')) return 'bg-orange-900/40 text-orange-300 border-orange-700/40'
  if (s.includes('playwright')) return 'bg-indigo-900/40 text-indigo-300 border-indigo-700/40'
  if (s.includes('searxng') || s.includes('crawl')) return 'bg-teal-900/40 text-teal-300 border-teal-700/40'

  return 'bg-slate-700/40 text-slate-300 border-slate-600'
}

function SkillSection({
  title,
  skills,
  colorClass,
  emptyText,
}: {
  title: string
  skills?: string[]
  colorClass: string
  emptyText: string
}) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-widest text-slate-500 mb-1.5">
        {title}
      </p>

      {skills && skills.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {skills.map((skill) => (
            <span
              key={skill}
              className={`text-[10px] px-2 py-1 rounded-full border ${colorClass}`}
            >
              {skill}
            </span>
          ))}
        </div>
      ) : (
        <p className="text-xs text-slate-500">{emptyText}</p>
      )}
    </div>
  )
}

function CoverageBar({
  label,
  value,
  colorClass,
}: {
  label: string
  value?: number | null
  colorClass: string
}) {
  const safeValue =
    typeof value === 'number' && Number.isFinite(value)
      ? Math.max(0, Math.min(100, value))
      : null

  return (
    <div className="space-y-1.5">
      <div className="flex justify-between items-center text-xs">
        <span className="text-slate-400">{label}</span>
        <span className="font-semibold text-slate-300">
          {safeValue === null ? 'N/A' : `${safeValue.toFixed(0)}%`}
        </span>
      </div>

      <div className="h-1.5 rounded-full bg-slate-700 overflow-hidden">
        {safeValue !== null && (
          <div
            className={`h-full rounded-full ${colorClass}`}
            style={{ width: `${safeValue}%` }}
          />
        )}
      </div>
    </div>
  )
}

const JobCard: React.FC<{ job: Job; rank: number }> = ({ job, rank }) => {
  const [showSkills, setShowSkills] = useState(false)
  const [showMatchDetails, setShowMatchDetails] = useState(false)

  const combined = job.combined_score ?? 0
  const ats = job.ats_score ?? 0
  const semantic = job.semantic_score ?? 0

  const colors = getScoreColors(combined)
  const sourceColor = getSourceColor(job.source || '')

  const matchedSkills = job.matched_skills ?? []
  const missingSkills = job.missing_skills ?? []
  const otherResumeSkills = job.other_resume_skills ?? []

  const hasMatchDetails =
    matchedSkills.length > 0 ||
    missingSkills.length > 0 ||
    otherResumeSkills.length > 0 ||
    job.job_requirement_coverage != null ||
    job.candidate_skill_coverage != null

  const hasApplyLink = Boolean(job.url && job.url !== 'N/A')

  return (
    <div className="relative bg-slate-800/70 backdrop-blur-sm border border-slate-700/60 rounded-2xl p-5 hover:border-slate-500 hover:shadow-xl hover:shadow-black/30 transition-all duration-300 group flex flex-col gap-3">

      {/* Rank + Source */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-mono text-slate-600">#{rank}</span>

        <span className={`text-[11px] px-2 py-0.5 rounded-full border ${sourceColor}`}>
          {job.source || 'Unknown'}
        </span>
      </div>

      {/* Title & Company */}
      <div>
        <h3 className="text-base font-bold text-slate-100 group-hover:text-blue-300 transition-colors leading-snug line-clamp-2">
          {job.title || 'Untitled Role'}
        </h3>

        <div className="flex items-center gap-1.5 mt-1 text-sm text-slate-400">
          <span className="font-medium text-slate-300">
            {job.company || 'Unknown'}
          </span>

          {job.location && (
            <>
              <span className="text-slate-600">•</span>

              <span className="flex items-center gap-0.5 text-xs">
                <svg
                  className="w-3 h-3 text-slate-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M17.657 16.657L13.414 20.9a2 2 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                </svg>

                {job.location}
              </span>
            </>
          )}
        </div>
      </div>

      {/* Description */}
      <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed">
        {job.description || 'No description available.'}
      </p>

      {/* Score Row */}
      <div className="flex items-center justify-between bg-slate-900/50 rounded-xl px-3 py-2 border border-slate-700/40">
        <ScoreBadge
          label="ATS"
          score={ats}
          colorClass={getScoreColors(ats).badge}
        />

        <div className="flex flex-col items-center">
          <span className="text-[10px] text-slate-500 uppercase tracking-widest mb-0.5">
            Combined
          </span>

          <div className={`text-lg font-black ${colors.ring}`}>
            {combined.toFixed(0)}%
          </div>
        </div>

        <ScoreBadge
          label="Semantic"
          score={semantic}
          colorClass={getScoreColors(semantic).badge}
        />
      </div>

      {/* Matched Skills Toggle */}
      {matchedSkills.length > 0 && (
        <div>
          <button
            type="button"
            onClick={() => setShowSkills((current) => !current)}
            className="text-[11px] text-slate-500 hover:text-blue-400 transition-colors"
          >
            {showSkills
              ? '▲ Hide matched skills'
              : `▼ ${matchedSkills.length} skills matched`}
          </button>

          {showSkills && (
            <div className="mt-2 flex flex-wrap gap-1">
              {matchedSkills.map((skill) => (
                <span
                  key={skill}
                  className="text-[10px] px-1.5 py-0.5 bg-blue-900/30 text-blue-300 border border-blue-800/40 rounded-full"
                >
                  {skill}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Why This Match */}
      {hasMatchDetails && (
        <div className="border border-slate-700/60 rounded-xl overflow-hidden">
          <button
            type="button"
            onClick={() => setShowMatchDetails((current) => !current)}
            className="w-full flex items-center justify-between px-3 py-2.5 text-left bg-slate-900/40 hover:bg-slate-900/70 transition-colors"
          >
            <span className="text-xs font-semibold text-slate-300">
              ✨ Why This Match?
            </span>

            <span className="text-xs text-slate-500">
              {showMatchDetails ? '−' : '+'}
            </span>
          </button>

          {showMatchDetails && (
            <div className="p-3 space-y-4">
              {/* Coverage */}
              <div className="space-y-3">
                <CoverageBar
                  label="Job Requirement Coverage"
                  value={job.job_requirement_coverage}
                  colorClass="bg-blue-500"
                />

                <CoverageBar
                  label="Candidate Skill Coverage"
                  value={job.candidate_skill_coverage}
                  colorClass="bg-emerald-500"
                />
              </div>

              {/* Skill counts */}
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-slate-900/50 rounded-lg p-2">
                  <p className="text-[10px] text-slate-500 uppercase tracking-wider">
                    Resume Skills
                  </p>
                  <p className="text-sm font-bold text-slate-200">
                    {job.resume_skill_count ?? 'N/A'}
                  </p>
                </div>

                <div className="bg-slate-900/50 rounded-lg p-2">
                  <p className="text-[10px] text-slate-500 uppercase tracking-wider">
                    Job Skills
                  </p>
                  <p className="text-sm font-bold text-slate-200">
                    {job.job_skill_count ?? 'N/A'}
                  </p>
                </div>
              </div>

              {/* Matched Skills */}
              <SkillSection
                title="Matched Skills"
                skills={matchedSkills}
                colorClass="bg-emerald-900/30 text-emerald-300 border-emerald-700/40"
                emptyText="No matched skills identified."
              />

              {/* Missing Skills */}
              <SkillSection
                title="Missing Job Skills"
                skills={missingSkills}
                colorClass="bg-rose-900/30 text-rose-300 border-rose-700/40"
                emptyText="No missing skills identified."
              />

              {/* Other Resume Skills */}
              <SkillSection
                title="Other Resume Skills"
                skills={otherResumeSkills}
                colorClass="bg-slate-700/50 text-slate-300 border-slate-600/50"
                emptyText="No additional resume skills identified."
              />

              <p className="text-[10px] leading-relaxed text-slate-500 border-t border-slate-700/50 pt-2">
                These scores are estimates based on the resume and job description.
                They are not an official ATS score or a guarantee of selection.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Apply Button */}
      <a
        href={hasApplyLink ? job.url : '#'}
        target="_blank"
        rel="noopener noreferrer"
        onClick={(e) => {
          if (!hasApplyLink) e.preventDefault()
        }}
        className={`mt-auto w-full py-2 rounded-xl text-center text-sm font-semibold transition-all duration-200 ${
          hasApplyLink
            ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-sm hover:shadow-blue-500/20 hover:shadow-md'
            : 'bg-slate-700 text-slate-500 cursor-not-allowed'
        }`}
      >
        {hasApplyLink ? 'Apply Now →' : 'Link Unavailable'}
      </a>
    </div>
  )
}

export default JobCard
